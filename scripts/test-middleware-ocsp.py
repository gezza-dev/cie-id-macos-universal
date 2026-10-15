#!/usr/bin/env python3
# SPDX-License-Identifier: BSD-3-Clause
"""Verify that the actual middleware rejects a malformed unsigned OCSP response.

Synthetic keys and documents are generated in a temporary directory and removed.
No real card, document or external service is used.
"""
import argparse,ctypes,datetime,http.server,json,os,subprocess,tempfile,threading
from pathlib import Path
parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('middleware',type=Path)
parser.add_argument('--openssl',required=True)
args=parser.parse_args()
fixture_directory=tempfile.TemporaryDirectory(prefix='cie-ocsp-regression-')
TEST=Path(fixture_directory.name)
OPENSSL=str(Path(args.openssl).resolve())
def call(*args):
    return subprocess.run([OPENSSL,*map(str,args)],cwd=TEST,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT,check=True,env={**os.environ,'OPENSSL_CONF':os.devnull})
def der(tag,data):
    n=len(data); length=bytes([n]) if n<128 else bytes([0x80+((n.bit_length()+7)//8)])+n.to_bytes((n.bit_length()+7)//8,'big')
    return bytes([tag])+length+data
def seq(*fields): return der(0x30,b''.join(fields))
# Deliberately lacks signatureAlgorithm, signature, signer certificate and valid CertID.
now=datetime.datetime.utcnow()
single=seq(seq(),der(0x80,b''),der(0x17,now.strftime('%y%m%d%H%M%SZ').encode()))
response_data=seq(der(0xa2,der(4,b'\0'*20)),der(0x18,now.strftime('%Y%m%d%H%M%SZ').encode()),seq(single))
basic=seq(response_data)
response=seq(der(0x0a,b'\0'),der(0xa0,seq(der(6,b'\x2b\x06\x01\x05\x05\x07\x30\x01\x01'),der(4,basic))))
(TEST/'unsigned-response.der').write_bytes(response)
class Handler(http.server.BaseHTTPRequestHandler):
    requests=0
    def do_POST(self):
        self.rfile.read(int(self.headers.get('Content-Length','0')))
        Handler.requests+=1
        self.send_response(200); self.send_header('Content-Type','application/ocsp-response'); self.end_headers(); self.wfile.write(response)
    def log_message(self,*args): pass
server=http.server.HTTPServer(('127.0.0.1',0),Handler)
thread=threading.Thread(target=server.serve_forever,daemon=True); thread.start()
try:
    url='http://127.0.0.1:'+str(server.server_port)+'/ocsp'
    call('req','-x509','-newkey','rsa:2048','-nodes','-keyout','fixture-key.pem','-out','fixture-cert.pem','-days','2','-subj','/CN=Local release audit fixture','-addext','basicConstraints=critical,CA:TRUE','-addext','keyUsage=critical,keyCertSign,cRLSign,digitalSignature','-addext','subjectKeyIdentifier=hash','-addext','authorityKeyIdentifier=keyid:always','-addext','authorityInfoAccess=OCSP;URI:'+url)
    (TEST/'document.txt').write_text('Local-only synthetic audit document\n')
    call('cms','-sign','-binary','-nodetach','-in','document.txt','-signer','fixture-cert.pem','-inkey','fixture-key.pem','-outform','DER','-out','document.p7m')
    class Info(ctypes.Structure):
        _fields_=[(n,ctypes.c_char*512) for n in ['name','surname','cn','signingTime','cadn']]+[('CertRevocStatus',ctypes.c_int),('isSignValid',ctypes.c_bool),('isCertValid',ctypes.c_bool)]
    lib=ctypes.CDLL(str(args.middleware.resolve()))
    lib.verificaConCIE.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_int,ctypes.c_char_p];lib.verificaConCIE.restype=ctypes.c_ulong
    lib.getVerifyInfo.argtypes=[ctypes.c_int,ctypes.POINTER(Info)];lib.getVerifyInfo.restype=ctypes.c_ulong
    count=lib.verificaConCIE(os.fsencode(TEST/'document.p7m'),None,0,None)
    info=Info(); status=lib.getVerifyInfo(0,ctypes.byref(info))
    openssl_parse=subprocess.run([OPENSSL,'ocsp','-respin',str(TEST/'unsigned-response.der'),'-text','-noverify'],text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
    report=dict(synthetic_local_fixture=True,external_connections=False,unsigned_ocsp_response=True,openssl_rejects_invalid_response=openssl_parse.returncode!=0,ocsp_requests_received=Handler.requests,middleware_signature_count=count,details_result=status,document_signature_valid=info.isSignValid,certificate_within_validity_period=info.isCertValid,reported_revocation_status=info.CertRevocStatus,unsigned_response_accepted_as_good=Handler.requests>0 and status==0 and info.CertRevocStatus==0)
    if count != 1 or status != 0 or Handler.requests < 1 or report['unsigned_response_accepted_as_good'] or info.CertRevocStatus != 3:
        raise RuntimeError('Middleware failed the unsigned OCSP regression: '+json.dumps(report))
    print(json.dumps(report,indent=2),flush=True)
finally:
    server.shutdown(); server.server_close(); fixture_directory.cleanup()

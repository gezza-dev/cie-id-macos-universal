//
//  MessageViewController.m
//
//  Copyright © 2024 IPZS. All rights reserved.
//

#import "AppDelegate.h"
#import "MessageViewController.h"
#import "AppPresentation.h"

@interface MessageViewController ()

@end

@implementation MessageViewController

- (void)viewDidLoad {
    [super viewDidLoad];
    // Do view setup here.
}

- (void)viewWillAppear {
    [super viewWillAppear];
    CIEWrapLabel(self.messageLabel, 440);
    CGFloat height = MAX(56, ceil([self.messageLabel.cell cellSizeForBounds:NSMakeRect(0, 0, 444, CGFLOAT_MAX)].height));
    self.messageLabel.frame = NSMakeRect(18, 41, 444, height);
    self.view.frame = NSMakeRect(0, 0, 480, height + 61);
    self.popover.contentSize = self.view.frame.size;
}

// MARK: Storyboard instantiation
+ (MessageViewController*) freshController {
    MessageViewController* vc = (MessageViewController*)[[MessageViewController alloc] initWithNibName:@"MessageViewController" bundle:nil];
    return vc;
}

- (IBAction)openCIEID:(NSButton*)sender {
    
    [(AppDelegate *)NSApp.delegate openCIEID:sender];
    
    if(sender && sender.tag == 100)
    {
        NSString* url = [NSUserDefaults.standardUserDefaults objectForKey:@"url"];
        [[NSWorkspace sharedWorkspace] openURL:[NSURL URLWithString: url]];
    }
    
    [_popover performClose:sender];
}

- (IBAction)close:(id)sender {
    [_popover performClose:sender];
}

@end

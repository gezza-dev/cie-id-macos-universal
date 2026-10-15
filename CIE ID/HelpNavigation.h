// SPDX-License-Identifier: BSD-3-Clause
#pragma once
#import <WebKit/WebKit.h>

typedef NS_ENUM(NSInteger, CIEHelpNavigationPolicy) {
    CIEHelpNavigationAllow,
    CIEHelpNavigationCancel,
    CIEHelpNavigationOpenExternally
};

// Only the bundled guide can be opened as a file. User-selected web links
// leave the app; the help/privacy pages can still load their own resources.
static inline CIEHelpNavigationPolicy CIEHelpPolicy(NSURL *url,
    WKNavigationType type, BOOL hasTargetFrame, NSURL *guideURL) {
    if (!url) return CIEHelpNavigationCancel;
    NSString *scheme = url.scheme.lowercaseString;
    if ([url.absoluteString isEqualToString:@"about:blank"] && hasTargetFrame && type != WKNavigationTypeLinkActivated)
        return CIEHelpNavigationAllow;
    if (url.isFileURL) {
        return guideURL && [url.URLByStandardizingPath.path isEqualToString:guideURL.URLByStandardizingPath.path]
            ? CIEHelpNavigationAllow : CIEHelpNavigationCancel;
    }
    if ([scheme isEqualToString:@"https"] || [scheme isEqualToString:@"http"]) {
        if (type == WKNavigationTypeLinkActivated) return CIEHelpNavigationOpenExternally;
        return hasTargetFrame ? CIEHelpNavigationAllow : CIEHelpNavigationCancel;
    }
    if ([scheme isEqualToString:@"mailto"] && type == WKNavigationTypeLinkActivated)
        return CIEHelpNavigationOpenExternally;
    return CIEHelpNavigationCancel;
}

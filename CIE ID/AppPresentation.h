// Presentation helpers shared by the main window and notification popovers.
#pragma once
#import <Cocoa/Cocoa.h>

static inline NSString *CIEDisplayVersion(void) {
    NSBundle *bundle = NSBundle.mainBundle;
    return [bundle objectForInfoDictionaryKey:@"CFBundleShortVersionString"];
}

static inline void CIEWrapLabel(NSTextField *label, CGFloat width) {
    label.cell.wraps = YES;
    label.cell.scrollable = NO;
    label.cell.usesSingleLineMode = NO;
    label.lineBreakMode = NSLineBreakByWordWrapping;
    label.maximumNumberOfLines = 0;
    label.preferredMaxLayoutWidth = width;
    [label setContentCompressionResistancePriority:NSLayoutPriorityRequired forOrientation:NSLayoutConstraintOrientationVertical];
}

static inline NSAlert *CIEMessageAlert(NSString *title, NSString *message, NSWindow *window) {
    NSAlert *alert = [[NSAlert alloc] init];
    alert.messageText = title;
    CGFloat width = MIN(440, window ? NSWidth(window.frame) - 160 : 440);
    CGFloat limit = MIN(300, window ? NSHeight(window.frame) - 240 : 300);
    NSScrollView *scroll = [[NSScrollView alloc] initWithFrame:NSMakeRect(0, 0, width, MAX(80, limit))];
    NSTextView *text = [[NSTextView alloc] initWithFrame:scroll.bounds];
    text.editable = NO;
    text.selectable = YES;
    text.drawsBackground = NO;
    text.font = [NSFont systemFontOfSize:NSFont.smallSystemFontSize];
    text.textContainerInset = NSMakeSize(0, 2);
    text.textContainer.lineFragmentPadding = 0;
    text.textContainer.containerSize = NSMakeSize(width - 18, CGFLOAT_MAX);
    text.textContainer.widthTracksTextView = NO;
    text.verticallyResizable = YES;
    text.string = message ?: @"";
    [text.layoutManager ensureLayoutForTextContainer:text.textContainer];
    CGFloat height = ceil(NSHeight([text.layoutManager usedRectForTextContainer:text.textContainer])) + 6;
    [text setFrameSize:NSMakeSize(width, height)];
    scroll.drawsBackground = NO;
    scroll.documentView = text;
    scroll.hasVerticalScroller = height > MAX(80, limit);
    [scroll setFrameSize:NSMakeSize(width, MIN(height, MAX(80, limit)))];
    alert.accessoryView = scroll;
    return alert;
}


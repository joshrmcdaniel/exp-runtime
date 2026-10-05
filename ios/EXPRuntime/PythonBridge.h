#import <Foundation/Foundation.h>

NS_ASSUME_NONNULL_BEGIN

/// Owns one embedded interpreter; invoke from the host's serial engine queue.
@interface PythonBridge : NSObject
- (nullable NSString *)request:(NSString *)json
                    directory:(NSString *)directory
                        error:(NSError * _Nullable * _Nullable)error;
@end

NS_ASSUME_NONNULL_END

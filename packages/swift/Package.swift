// swift-tools-version: 5.9
import PackageDescription

let package = Package(
    name: "UsermonSDK",
    platforms: [
        .iOS(.v14),
        .macOS(.v11),
        .tvOS(.v14),
        .watchOS(.v7),
    ],
    products: [
        .library(
            name: "UsermonSDK",
            targets: ["UsermonSDK"]
        ),
    ],
    targets: [
        .target(
            name: "UsermonSDK",
            path: "Sources/UsermonSDK"
        ),
        .testTarget(
            name: "UsermonSDKTests",
            dependencies: ["UsermonSDK"],
            path: "Tests/UsermonSDKTests"
        ),
    ]
)

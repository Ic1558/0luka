// swift-tools-version: 6.2
// The swift-tools-version declares the minimum version of Swift required to build this package.

import PackageDescription

let package = Package(
    name: "design-lane-macos",
    platforms: [
        .macOS(.v13)
    ],
    products: [
        .executable(name: "design-lane-macos", targets: ["design-lane-macos"]),
        .library(name: "DesignLaneCore", targets: ["DesignLaneCore"]),
        .library(name: "DesignLaneAPI", targets: ["DesignLaneAPI"])
    ],
    targets: [
        .target(
            name: "DesignLaneCore"
        ),
        .target(
            name: "DesignLaneAPI",
            dependencies: [
                "DesignLaneCore"
            ]
        ),
        .executableTarget(
            name: "design-lane-macos",
            dependencies: [
                "DesignLaneAPI",
                "DesignLaneCore"
            ]
        ),
        .executableTarget(
            name: "Verification",
            dependencies: ["DesignLaneCore"]
        ),
    ]
)

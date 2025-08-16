// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract FirmwareRegistry {
    struct Release {
        string uri;        // e.g., https://forti-ota-pi.local/ipfs/<CID>
        bytes32 sha256sum; // SHA-256 of the exact firmware .bin (as 0x...32 bytes)
        uint256 version;   // monotonically increasing
        uint256 timestamp; // block time
    }

    mapping(string => uint256) public latestVersion;
    mapping(string => mapping(uint256 => Release)) public releases;

    event ReleasePublished(string indexed deviceType, uint256 version, string uri, bytes32 sha256sum);
    event Ack(string indexed deviceId, string indexed deviceType, uint256 version, bool success, string info);

    function publish(string memory deviceType, uint256 version, string memory uri, bytes32 sha256sum) public {
        require(version > latestVersion[deviceType], "non-incrementing");
        releases[deviceType][version] = Release(uri, sha256sum, version, block.timestamp);
        latestVersion[deviceType] = version;
        emit ReleasePublished(deviceType, version, uri, sha256sum);
    }

    function getLatest(string memory deviceType)
        public view
        returns (uint256 version, string memory uri, bytes32 sha256sum)
    {
        uint256 v = latestVersion[deviceType];
        require(v != 0, "no release");
        Release storage r = releases[deviceType][v];
        return (r.version, r.uri, r.sha256sum);
    }

    function ack(string memory deviceId, string memory deviceType, uint256 version, bool success, string memory info) public {
        emit Ack(deviceId, deviceType, version, success, info);
    }
}

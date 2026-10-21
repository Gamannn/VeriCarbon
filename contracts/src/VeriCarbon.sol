// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {AccessControl} from "@openzeppelin/contracts/access/AccessControl.sol";
import {ReentrancyGuard} from "@openzeppelin/contracts/utils/ReentrancyGuard.sol";

contract VeriCarbon is AccessControl, ReentrancyGuard {
    // ──────────────────── Roles ────────────────────
    bytes32 public constant VALIDATOR_ROLE = keccak256("VALIDATOR_ROLE");
    bytes32 public constant BACKEND_ROLE = keccak256("BACKEND_ROLE");

    // ──────────────────── Enums ────────────────────
    enum State {
        None,
        Pending,
        Flagged,
        Verified,
        Issued,
        Rejected
    }

    // ──────────────────── Structs ────────────────────
    struct Project {
        address submitter;
        State state;
        uint64 claimedAreaHa;
        uint64 verifiedAreaHa;
        uint16 confidenceBps;
        uint8 attestationCount;
        uint40 submittedAt;
        uint40 lastUpdatedAt;
        bytes32 datasetHash;
        bytes32 modelHash;
        bytes32 resultHash;
        bytes32 registryRefsHash;
    }

    struct Attestation {
        address validator;
        bytes32 datasetHash;
        bytes32 modelHash;
        bytes32 resultHash;
        uint64 verifiedAreaHa;
        uint16 confidenceBps;
        uint40 timestamp;
    }

    // ──────────────────── Constants ────────────────────
    uint8 public constant ATTESTATION_THRESHOLD = 2;

    // ──────────────────── Storage ────────────────────
    mapping(bytes32 => Project) private _projects;
    mapping(bytes32 => Attestation[]) private _attestations;
    mapping(bytes32 => mapping(address => bool)) private _hasAttested;
    mapping(uint64 => bytes32) private _cellOwner;

    bytes32[] private _projectIds;

    // ──────────────────── Events ────────────────────
    event ProjectSubmitted(
        bytes32 indexed projectId,
        address indexed submitter,
        uint64 claimedAreaHa,
        uint256 cellCount
    );
    event VerificationAttested(
        bytes32 indexed projectId,
        address indexed validator,
        uint8 attestationCount
    );
    event ProjectVerified(bytes32 indexed projectId, uint64 verifiedAreaHa, uint16 confidenceBps);
    event ProjectFlagged(bytes32 indexed projectId, address indexed flaggedBy, string reason);
    event FlagResolved(bytes32 indexed projectId, bool accepted);
    event CreditIssued(bytes32 indexed projectId, uint64 verifiedAreaHa);
    event ProjectRejected(bytes32 indexed projectId);

    // ──────────────────── Errors ────────────────────
    error ProjectAlreadyExists();
    error ProjectNotFound();
    error InvalidState(State current, State required);
    error CellAlreadyClaimed(uint64 cell, bytes32 owner);
    error NoCells();
    error AlreadyAttested();
    error ZeroArea();
    error ConfidenceOutOfRange();

    // ──────────────────── Constructor ────────────────────
    constructor() {
        _grantRole(DEFAULT_ADMIN_ROLE, msg.sender);
        _grantRole(BACKEND_ROLE, msg.sender);
        _grantRole(VALIDATOR_ROLE, msg.sender);
    }

    // ──────────────────── Submit ────────────────────
    function submitProject(
        bytes32 projectId,
        uint64[] calldata cells,
        uint64 claimedAreaHa,
        bytes32 registryRefsHash
    ) external onlyRole(BACKEND_ROLE) {
        if (_projects[projectId].state != State.None) revert ProjectAlreadyExists();
        if (cells.length == 0) revert NoCells();
        if (claimedAreaHa == 0) revert ZeroArea();

        for (uint256 i = 0; i < cells.length; i++) {
            bytes32 owner = _cellOwner[cells[i]];
            if (owner != bytes32(0)) revert CellAlreadyClaimed(cells[i], owner);
            _cellOwner[cells[i]] = projectId;
        }

        Project storage p = _projects[projectId];
        p.submitter = msg.sender;
        p.state = State.Pending;
        p.claimedAreaHa = claimedAreaHa;
        p.submittedAt = uint40(block.timestamp);
        p.lastUpdatedAt = uint40(block.timestamp);
        p.registryRefsHash = registryRefsHash;

        _projectIds.push(projectId);

        emit ProjectSubmitted(projectId, msg.sender, claimedAreaHa, cells.length);
    }

    // ──────────────────── Attest ────────────────────
    function attestVerification(
        bytes32 projectId,
        bytes32 datasetHash,
        bytes32 modelHash,
        bytes32 resultHash,
        uint64 verifiedAreaHa,
        uint16 confidenceBps
    ) external onlyRole(VALIDATOR_ROLE) {
        Project storage p = _projects[projectId];
        if (p.state != State.Pending && p.state != State.Flagged) {
            revert InvalidState(p.state, State.Pending);
        }
        if (_hasAttested[projectId][msg.sender]) revert AlreadyAttested();
        if (confidenceBps > 10000) revert ConfidenceOutOfRange();

        _hasAttested[projectId][msg.sender] = true;

        _attestations[projectId].push(
            Attestation({
                validator: msg.sender,
                datasetHash: datasetHash,
                modelHash: modelHash,
                resultHash: resultHash,
                verifiedAreaHa: verifiedAreaHa,
                confidenceBps: confidenceBps,
                timestamp: uint40(block.timestamp)
            })
        );

        p.attestationCount++;
        p.lastUpdatedAt = uint40(block.timestamp);

        emit VerificationAttested(projectId, msg.sender, p.attestationCount);

        if (p.attestationCount >= ATTESTATION_THRESHOLD) {
            _finalizeVerification(projectId);
        }
    }

    // ──────────────────── Flag ────────────────────
    function flagProject(bytes32 projectId, string calldata reason)
        external
        onlyRole(VALIDATOR_ROLE)
    {
        Project storage p = _projects[projectId];
        if (p.state != State.Pending) revert InvalidState(p.state, State.Pending);

        p.state = State.Flagged;
        p.lastUpdatedAt = uint40(block.timestamp);

        emit ProjectFlagged(projectId, msg.sender, reason);
    }

    // ──────────────────── Resolve Flag ────────────────────
    function resolveFlag(bytes32 projectId, bool accept, uint64[] calldata cells)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        Project storage p = _projects[projectId];
        if (p.state != State.Flagged) revert InvalidState(p.state, State.Flagged);

        if (accept) {
            p.state = State.Pending;
            p.lastUpdatedAt = uint40(block.timestamp);
            emit FlagResolved(projectId, true);
        } else {
            _rejectProject(projectId, cells);
            emit FlagResolved(projectId, false);
        }
    }

    // ──────────────────── Issue Credit ────────────────────
    function issueClaim(bytes32 projectId) external onlyRole(DEFAULT_ADMIN_ROLE) nonReentrant {
        Project storage p = _projects[projectId];
        if (p.state != State.Verified) revert InvalidState(p.state, State.Verified);

        p.state = State.Issued;
        p.lastUpdatedAt = uint40(block.timestamp);

        emit CreditIssued(projectId, p.verifiedAreaHa);
    }

    // ──────────────────── Reject ────────────────────
    function rejectProject(bytes32 projectId, uint64[] calldata cells)
        external
        onlyRole(DEFAULT_ADMIN_ROLE)
    {
        Project storage p = _projects[projectId];
        if (p.state == State.None || p.state == State.Issued || p.state == State.Rejected) {
            revert InvalidState(p.state, State.Pending);
        }
        _rejectProject(projectId, cells);
    }

    // ──────────────────── Views ────────────────────
    function getProject(bytes32 projectId)
        external
        view
        returns (
            address submitter,
            State state,
            uint64 claimedAreaHa,
            uint64 verifiedAreaHa,
            uint16 confidenceBps,
            uint8 attestationCount,
            uint40 submittedAt,
            uint40 lastUpdatedAt,
            bytes32 datasetHash,
            bytes32 modelHash,
            bytes32 resultHash
        )
    {
        Project storage p = _projects[projectId];
        if (p.state == State.None) revert ProjectNotFound();
        return (
            p.submitter,
            p.state,
            p.claimedAreaHa,
            p.verifiedAreaHa,
            p.confidenceBps,
            p.attestationCount,
            p.submittedAt,
            p.lastUpdatedAt,
            p.datasetHash,
            p.modelHash,
            p.resultHash
        );
    }

    function getRegistryRefsHash(bytes32 projectId) external view returns (bytes32) {
        if (_projects[projectId].state == State.None) revert ProjectNotFound();
        return _projects[projectId].registryRefsHash;
    }

    function getAttestations(bytes32 projectId) external view returns (Attestation[] memory) {
        return _attestations[projectId];
    }

    function getCellOwner(uint64 cell) external view returns (bytes32) {
        return _cellOwner[cell];
    }

    function getProjectCount() external view returns (uint256) {
        return _projectIds.length;
    }

    function getProjectIdAt(uint256 index) external view returns (bytes32) {
        return _projectIds[index];
    }

    // ──────────────────── Internal ────────────────────
    function _finalizeVerification(bytes32 projectId) internal {
        Project storage p = _projects[projectId];
        Attestation[] storage atts = _attestations[projectId];

        uint256 totalArea = 0;
        uint256 totalConf = 0;
        for (uint256 i = 0; i < atts.length; i++) {
            totalArea += atts[i].verifiedAreaHa;
            totalConf += atts[i].confidenceBps;
        }

        uint256 avgArea = totalArea / atts.length;
        uint256 avgConf = totalConf / atts.length;
        p.verifiedAreaHa = avgArea > type(uint64).max ? type(uint64).max : uint64(avgArea);
        p.confidenceBps = avgConf > 10000 ? uint16(10000) : uint16(avgConf);
        p.datasetHash = atts[atts.length - 1].datasetHash;
        p.modelHash = atts[atts.length - 1].modelHash;
        p.resultHash = atts[atts.length - 1].resultHash;
        p.state = State.Verified;
        p.lastUpdatedAt = uint40(block.timestamp);

        emit ProjectVerified(projectId, p.verifiedAreaHa, p.confidenceBps);
    }

    function _rejectProject(bytes32 projectId, uint64[] memory cells) internal {
        Project storage p = _projects[projectId];
        p.state = State.Rejected;
        p.lastUpdatedAt = uint40(block.timestamp);

        for (uint256 i = 0; i < cells.length; i++) {
            if (_cellOwner[cells[i]] == projectId) {
                delete _cellOwner[cells[i]];
            }
        }

        emit ProjectRejected(projectId);
    }
}

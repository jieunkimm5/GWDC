// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract DecisionRegistry {

    struct Record {
        string run_id;
        string decision;
        bool approved;
        string amount;
        string provider;
        uint256 timestamp;
    }

    mapping(string => Record) private records;

    event DecisionRecorded(
        string run_id,
        string decision,
        bool approved,
        string amount,
        string provider,
        uint256 timestamp
    );

    function recordDecision(
        string memory _run_id,
        string memory _decision,
        bool _approved,
        string memory _amount,
        string memory _provider
    ) public {

        records[_run_id] = Record(
            _run_id,
            _decision,
            _approved,
            _amount,
            _provider,
            block.timestamp
        );

        emit DecisionRecorded(
            _run_id,
            _decision,
            _approved,
            _amount,
            _provider,
            block.timestamp
        );
    }

    function getRecord(
        string memory _run_id
    )
        public
        view
        returns (
            string memory,
            string memory,
            bool,
            string memory,
            string memory,
            uint256
        )
    {
        Record memory r = records[_run_id];

        return (
            r.run_id,
            r.decision,
            r.approved,
            r.amount,
            r.provider,
            r.timestamp
        );
    }
}
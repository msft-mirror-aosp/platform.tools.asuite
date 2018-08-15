#!/bin/bash

RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color
AIDEGEN_DIR=$(dirname $(realpath $0))

function print_summary() {
    local test_results=$1

    if [[ $test_results -eq 0 ]]; then
        echo -e "${GREEN}All unittests pass${NC}!"
    else
        echo -e "${RED}There was a unittest failure${NC}"
    fi
}

function run_unittests() {
    local specified_tests=$@
    local rc=0

    # Get all unit tests under tools/acloud.
    local all_tests=$(find $AIDEGEN_DIR -type f -name "*_unittest.py");
    local tests_to_run=$all_tests

    for t in $tests_to_run;
    do
        if ! PYTHONPATH=../ python $t; then
            rc=1
            echo -e "${RED}$t failed${NC}"
        fi
    done

    print_summary $rc
    cleanup
}

function check_env() {
    if [ -z "$ANDROID_BUILD_TOP" ]; then
        echo "Missing ANDROID_BUILD_TOP env variable. Run 'lunch' first."
        exit 1
    fi
}

function cleanup() {
    # Search for *.pyc and delete them.
    find $AIDEGEN_DIR -name "*.pyc" -exec rm -f {} \;
}

check_env
cleanup
run_unittests $@

import sys
import os
import pickle
import sys

from pathlib import Path

from atest import atest_arg_parser
from atest import constants

def fetch_atest_args():
    parser = atest_arg_parser.AtestArgParser()
    parser.add_atest_args()
    print("\n".join(parser.get_args()))


def fetch_testable_modules():
    index_dir = Path(os.getenv(constants.ANDROID_HOST_OUT)).joinpath('indexes')
    module_index = index_dir.joinpath(constants.MODULE_INDEX)
    if os.path.isfile(module_index):
        with open(module_index, 'rb') as cache:
            try:
                print("\n".join(pickle.load(cache, encoding="utf-8")))
            except:
                print("\n".join(pickle.load(cache)))
    else:
        print("")

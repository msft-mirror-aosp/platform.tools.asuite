# Copyright 2019, The Android Open Source Project
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# Shared variables
OS_ARCH="$(uname -s | tr [:upper:] [:lower:])-x86"
# Colors
BOLD="$(tput bold)"
UNDERLINE="$(tput smul)"
END="$(tput sgr0)"
BLINK="$(tput blink)"
GREEN="$(tput setaf 2)"
RED="$(tput setaf 198)"

_MIN_WINDOW_WIDTH=86

# set_asuite_vars() establishes variables used by _list() and _configure().
#     args: none
#     return: none
function set_asuite_vars() {
    # This check is to adapt users who only "source envsetup.sh" without lunch.
    if [ -z ${ANDROID_BUILD_TOP:-} ]; then
        echo "Local variable \$ANDROID_BUILD_TOP was not found."
        echo -e "Have you forgotten to run$BOLD$BLINK$GREEN lunch$END?"
        return 1
    fi

    ATEST_PREBUILT=\$ANDROID_BUILD_TOP/prebuilts/asuite/atest/$OS_ARCH/atest
    ATEST_BUILT=\$ANDROID_HOST_OUT/bin/atest
    ATEST_SOONGBUILT=$ANDROID_BUILD_TOP/out/soong/host/$OS_ARCH/bin/atest
    ATEST_SRC=\$ANDROID_BUILD_TOP/tools/tradefederation/core/atest/atest.py
    ATEST_MATRIX="prebuilt   $(eval echo $ATEST_PREBUILT)   $ATEST_PREBUILT
                  built      $(eval echo $ATEST_BUILT)      $ATEST_BUILT
                  source     $(eval echo $ATEST_SRC)        $ATEST_SRC"

    ACLOUD_PREBUILT=\$ANDROID_BUILD_TOP/prebuilts/asuite/acloud/$OS_ARCH/acloud
    ACLOUD_BUILT=\$ANDROID_HOST_OUT/bin/acloud
    ACLOUD_SOONGBUILT=$ANDROID_BUILD_TOP/out/soong/host/$OS_ARCH/bin/acloud
    ACLOUD_MATRIX="prebuilt   $(eval echo $ACLOUD_PREBUILT)   $ACLOUD_PREBUILT
                   built      $(eval echo $ACLOUD_BUILT)      $ACLOUD_BUILT"

    AIDEGEN_PREBUILT=\$ANDROID_BUILD_TOP/prebuilts/asuite/aidegen/$OS_ARCH/aidegen
    AIDEGEN_BUILT=\$ANDROID_HOST_OUT/bin/aidegen
    AIDEGEN_SOONGBUILT=$ANDROID_BUILD_TOP/out/soong/host/$OS_ARCH/bin/aidegen
    AIDEGEN_MATRIX="prebuilt   $(eval echo $AIDEGEN_PREBUILT)   $AIDEGEN_PREBUILT
                    built      $(eval echo $AIDEGEN_BUILT)      $AIDEGEN_BUILT"

    # Ensure only using $ANDROID_HOST_OUT/bin/*
    for executable in $ATEST_SOONGBUILT $ACLOUD_SOONGBUILT $AIDEGEN_SOONGBUILT; do
        rm -f $executable
    done
}

# _is_selected() can check whether the target is in PATH/aliased or not.
#     args: absolute path of target atest/acloud/aidegen.
#     return: 0 if it is currently selected.
function _is_selected() {
    target_path=$1
    target=$(basename $target_path .py)
    # if aliased, ensure it exists otherwise unalias it and check again.
    if [ -n "$(alias | grep $target ||true)" ]; then
        aliased_path=
        # fetch absolute path from bash and zsh.
        if [ -n "$BASH_VERSION" ]; then
            aliased_path="$(alias|grep $target|awk -F'=' '{print $2}')"
            aliased_path="${aliased_path//\'/}"
        elif [ -n "$ZSH_VERSION" ]; then
            aliased_path="$(type $target|awk '{print $6}')"
        fi
        if [ -x "$aliased_path" ]; then
            if [ "$aliased_path" != "$target_path" ]; then
                return 1
            else
                return 0
            fi
        else
            unalias $target
            ${FUNCNAME[0]}${funcstack[1]} $target_path
        fi
    fi
    # if not aliased, check if it's the priority in PATH.
    if [ "$(which $target)" != "$target_path" ]; then
       return 1
    fi
    return 0
}

# _print_content() prints content with the pre-defined format.
#    args: type, abs_path, ref_path, last_modified_time(mtime)
#    return: type ref_path mtime
function _print_content() {
    type_of=$1
    abs_path=$2
    ref_path=$3
    mtime=$4
    if [ $(tput cols) -ge $_MIN_WINDOW_WIDTH ]; then
        format='%9s %-62s %-14s\n'
        # add "*" when it is selected.
        printf "$format" "$type_of" "$ref_path" "$mtime"
    else
        format='%9s %-62s\n'
        printf "$format" "$type_of" "$ref_path"
    fi
}

function _print_header() {
    if [ $(tput cols) -ge $_MIN_WINDOW_WIDTH ]; then
       format='%19s %-72s %-14s\n'
       printf "$format" "${UNDERLINE}TYPE$END" "${UNDERLINE}REFERENCE TYPE$END" "${UNDERLINE}TIME$END"
    else
       format='%19s %-72s\n'
       printf "$format" "${UNDERLINE}TYPE$END" "${UNDERLINE}REFERENCE TYPE$END"
    fi
}

# _list_matrix() returns the *_MATRIX variable by reading the target name.
#     args: target (atest/acloud/aidegen).
#     return: the content of *_MATRIX variable.
function _list_matrix() {
    case $1 in
        aidegen)
          echo "$AIDEGEN_MATRIX" ;;
        acloud)
          echo "$ACLOUD_MATRIX" ;;
        atest)
          echo "$ATEST_MATRIX" ;;
    esac
}

# _list() is to print type, reference_path and time in predefined format.
#     args: target (atest/acloud/aidegen).
#     return: _print_content
function _list() {
    set_asuite_vars || return 1
    target=$1
    _print_header
    while read line; do
        type_of=$(echo $line|awk '{print $1}')
        abs_path=$(echo $line|awk '{print $2}')
        ref_path=$(echo $line|awk '{print $3}')
        mtime=$(LC_ALL=en_US.UTF-8 ls -lL $abs_path 2>/dev/null\
                | awk '{printf "%3s %2s %5s", $6, $7, $8}')
        _is_selected $abs_path
        _print_content "$type_of$([ "$?" -eq 0 ] && echo '*')" "$abs_path" "$ref_path" "$mtime"
    done < <(_list_matrix $target)
}

# _configure() is to alias atest/acloud/aidegen with the corresponding
# absolute path, and print result after selection.
#     args: target (atest/acloud/aidegen).
#     return: target.list
function _configure() {
    function _alias() {
        target=$1
        choice=$2
        abs_path=$3
        if [ -x $abs_path ]; then
            alias $target=$abs_path
        else
            echo -n "$target $BOLD$RED$choice$END is unavailable. "
            echo -e "Select prebuilt or run:$BOLD$BLINK$GREEN m $target$END to create one."
        fi
    }
    set_asuite_vars || return 1
    target=$1
    unalias $target 2>/dev/null || true
    echo -n "Which $target ("
    while read line; do
        [ "$line" == "prebuilt" ] && echo -n "[$line] " || echo -n " / $line"
    done < <(while read line; do echo $line| awk '{print $1}'; done < <(_list_matrix $target))
    echo -n ") do you wanna run with? "
    read selection
    case $selection in
        built)
            abs_path="$(_list_matrix $target|sed 's/^[ ]*//g'|egrep ^built| awk '{print $2}')"
            _alias $target $selection $abs_path ;;
        source)
            alias $target="$(_list_matrix $target|sed 's/^[ ]*//g'|egrep ^sourc | awk '{print $2}')"
            ;;
        *)
            # selecting prebuilt by default.
            abs_path="$(_list_matrix $target|sed 's/^[ ]*//g'|egrep ^prebuilt| awk '{print $2}')"
            alias $target=$abs_path ;;
    esac
    $target.list
}


# Main function.
function _main() {
    local T="$(gettop)/tools"
    src_atest="$T/tradefederation/core/atest/atest_completion.sh"
    src_acloud="$T/acloud/acloud_completion.sh"
    src_aidegen="$T/asuite/aidegen/aidegen_completion.sh"
    declare -a asuite_srcs=($src_atest $src_acloud $src_aidegen)
    for src in ${asuite_srcs[@]}; do [[ -f $src ]] && source $src || true; done

    # Add asuite functions.
    # FUNCNAME(bash) and funcstack(zsh) are used to determine which target to run.
    atest.list() { _list $(echo ${FUNCNAME[0]}${funcstack[1]}| awk -F. '{print $1}'); }
    atest.config() { _configure $(echo ${FUNCNAME[0]}${funcstack[1]}| awk -F. '{print $1}'); }
    acloud.list() { _list $(echo ${FUNCNAME[0]}${funcstack[1]}| awk -F. '{print $1}'); }
    acloud.config() { _configure $(echo ${FUNCNAME[0]}${funcstack[1]}| awk -F. '{print $1}'); }
    aidegen.list() { _list $(echo ${FUNCNAME[0]}${funcstack[1]}| awk -F. '{print $1}'); }
    aidegen.config() { _configure $(echo ${FUNCNAME[0]}${funcstack[1]}| awk -F. '{print $1}'); }
}

_main

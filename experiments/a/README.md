# A tool

A tool is a command-line tool that can run android workflows and productivity tools
go/a-tool-design-doc

Contributions welcome!

### A and Autocomplete aliases
Add the following to your  ~/.bashrc for autocompletions
```
# Alias for local workflow "a update" tool
a() {
    python3 "$ANDROID_BUILD_TOP/tools/asuite/experiments/a/a.py" "$@"
}
_a_completion() {
  local cur prev opts
  COMPREPLY=()
  cur="${COMP_WORDS[COMP_CWORD]}"
  prev="${COMP_WORDS[COMP_CWORD-1]}"

  if [[ ${prev} == "a" ]] ; then
    COMPREPLY=( $(compgen -W "update" -- ${cur}) )
    return 0
  fi

  if [[ ${prev} == "update" ]] ; then
    COMPREPLY=( $(compgen -W "$(a update --list-aliases)" -- ${cur}) )
    return 0
  fi
}
complete -F _a_completion a
```

### To Run
```a {config_name}```
or
```python3 a.py {config_name}```

### To develop
```python3 a.py {config_name}```

### To Test:
or
```python3 -m unittest **/*_test.py```
or
```python3 tests.py``
or
```atest .```

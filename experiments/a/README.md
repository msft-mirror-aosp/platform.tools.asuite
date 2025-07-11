# `a` tool

`a` is a command-line tool that can run Android workflows and productivity tools.
For more information, see the design doc at go/a-tool-design-doc.

Contributions welcome!

## Setup: Aliases and Autocomplete

### Bash
Add the following to your  `~/.bashrc` to enable the `a` command and its autocompletion.
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

### Zsh
Add the following to your `~/.zshrc` to enable the `a` command and its autocompletion.
```
# Turn on auto completion
autoload -U compinit
compinit

# Alias for local workflow "a update" tool
a() {
    python3 "$ANDROID_BUILD_TOP/tools/asuite/experiments/a/a.py" "$@"
}
_a_completion() {
    local state

    _arguments \
        '1: :->command' \
        '*:: :->args'

    case $state in
        command)
            _values 'command' 'update'
            ;;
        args)
            case ${words[1]} in
                update)
                    _arguments '*:alias:_values "alias" $(a update --list-aliases)'
                    ;;
            esac
            ;;
    esac
}
compdef _a_completion a
```

## Running and Developing
You can run the tool using either the `a` alias (if configured) or by directly invoking the script:
```a {config_name}```
or
```python3 a.py {config_name}```

## Testing
Run the tests using any of the following commands:
```python3 -m unittest **/*_test.py```
or
```python3 tests.py``
or
```atest .```

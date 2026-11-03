# Directory Structure

```
.cargo/
  config.toml (18 lines)
.github/
  ISSUE_TEMPLATE/
    bug_report.yml (71 lines)
    config.yml (19 lines)
    feature_request.md (20 lines)
  workflows/
    coverage.yaml (63 lines)
    napi.yml (162 lines)
    pyo3.yml (167 lines)
    pypi.yml (196 lines)
    release.yml (123 lines)
    wasm.yml (112 lines)
  CONTRIBUTING.md (9 lines)
  copilot-instructions.md (136 lines)
  FUNDING.yml (3 lines)
crates/
  cli/
    src/
      bin/
        alias.rs (16 lines)
      lang/
        injection.rs (275 lines)
        lang_globs.rs (166 lines)
        mod.rs (234 lines)
      print/
        colored_print/
          markdown.rs (52 lines)
          match_merger.rs (71 lines)
          styles.rs (164 lines)
          test.rs (342 lines)
        cloud_print.rs (434 lines)
        colored_print.rs (456 lines)
        file_name_printer.rs (105 lines)
        interactive_print.rs (524 lines)
        json_print.rs (767 lines)
        mod.rs (187 lines)
      utils/
        args.rs (372 lines)
        debug_query.rs (355 lines)
        error_context.rs (475 lines)
        inspect.rs (296 lines)
        mod.rs (220 lines)
        print_diff.rs (131 lines)
        rule_overwrite.rs (142 lines)
        worker.rs (323 lines)
      verify/
        case_result.rs (231 lines)
        find_file.rs (210 lines)
        reporter.rs (508 lines)
        snapshot.rs (235 lines)
        test_case.rs (200 lines)
      completions.rs (87 lines)
      config.rs (285 lines)
      lib.rs (320 lines)
      lsp.rs (49 lines)
      main.rs (8 lines)
      new.rs (424 lines)
      run.rs (466 lines)
      scan.rs (536 lines)
      verify.rs (365 lines)
    tests/
      common/
        mod.rs (21 lines)
      help_test.rs (18 lines)
      run_test.rs (150 lines)
      scan_test.rs (713 lines)
      verify_test.rs (142 lines)
    Cargo.toml (66 lines)
  config/
    src/
      rule/
        deserialize_env.rs (328 lines)
        mod.rs (679 lines)
        nth_child.rs (422 lines)
        range.rs (276 lines)
        referent_rule.rs (270 lines)
        relational_rule.rs (728 lines)
        selector.rs (394 lines)
        stop_by.rs (271 lines)
      transform/
        mod.rs (179 lines)
        parse.rs (253 lines)
        rewrite.rs (365 lines)
        string_case.rs (284 lines)
        trans.rs (465 lines)
      check_var.rs (329 lines)
      combined.rs (480 lines)
      fixer.rs (353 lines)
      label.rs (156 lines)
      lib.rs (233 lines)
      maybe.rs (150 lines)
      rule_collection.rs (385 lines)
      rule_config.rs (899 lines)
      rule_core.rs (450 lines)
    Cargo.toml (29 lines)
  core/
    src/
      match_tree/
        match_node.rs (332 lines)
        mod.rs (339 lines)
        strictness.rs (233 lines)
      matcher/
        kind.rs (145 lines)
        node_match.rs (145 lines)
        pattern.rs (726 lines)
        text.rs (43 lines)
      replacer/
        indent.rs (423 lines)
        structural.rs (213 lines)
        template.rs (359 lines)
      tree_sitter/
        mod.rs (525 lines)
        traversal.rs (601 lines)
      language.rs (79 lines)
      lib.rs (95 lines)
      matcher.rs (140 lines)
      meta_var.rs (389 lines)
      node.rs (572 lines)
      ops.rs (557 lines)
      pinned.rs (162 lines)
      replacer.rs (113 lines)
      source.rs (181 lines)
    Cargo.toml (26 lines)
  dynamic/
    src/
      custom_lang.rs (113 lines)
      lib.rs (356 lines)
    Cargo.toml (24 lines)
  language/
    src/
      bash.rs (40 lines)
      cpp.rs (45 lines)
      csharp.rs (27 lines)
      css.rs (29 lines)
      elixir.rs (92 lines)
      go.rs (59 lines)
      haskell.rs (66 lines)
      hcl.rs (61 lines)
      html.rs (159 lines)
      json.rs (38 lines)
      kotlin.rs (54 lines)
      lib.rs (610 lines)
      lua.rs (36 lines)
      nix.rs (54 lines)
      parsers.rs (110 lines)
      php.rs (17 lines)
      python.rs (123 lines)
      ruby.rs (32 lines)
      rust.rs (90 lines)
      scala.rs (52 lines)
      solidity.rs (53 lines)
      swift.rs (59 lines)
      yaml.rs (57 lines)
    Cargo.toml (80 lines)
  lsp/
    src/
      lib.rs (759 lines)
      utils.rs (257 lines)
    tests/
      basic.rs (693 lines)
    Cargo.toml (40 lines)
  napi/
    __test__/
      custom.spec.ts (62 lines)
      index.spec.ts (461 lines)
      test.vue (23 lines)
      type.spec.ts (217 lines)
    lang/
      .gitkeep (0 lines)
    npm/
      darwin-arm64/
        package.json (31 lines)
        README.md (3 lines)
      darwin-x64/
        package.json (31 lines)
        README.md (3 lines)
      linux-arm64-gnu/
        package.json (34 lines)
        README.md (3 lines)
      linux-arm64-musl/
        package.json (34 lines)
        README.md (3 lines)
      linux-x64-gnu/
        package.json (34 lines)
        README.md (3 lines)
      linux-x64-musl/
        package.json (34 lines)
        README.md (3 lines)
      win32-arm64-msvc/
        package.json (31 lines)
        README.md (3 lines)
      win32-ia32-msvc/
        package.json (31 lines)
        README.md (3 lines)
      win32-x64-msvc/
        package.json (31 lines)
        README.md (3 lines)
    scripts/
      constants.ts (20 lines)
      generateTypes.ts (97 lines)
    src/
      doc.rs (215 lines)
      find_files.rs (230 lines)
      lib.rs (127 lines)
      napi_lang.rs (326 lines)
      sg_node.rs (439 lines)
    types/
      api.d.ts (46 lines)
      config.d.ts (39 lines)
      deprecated.d.ts (117 lines)
      lang.d.ts (11 lines)
      registerDynamicLang.d.ts (27 lines)
      rule.d.ts (98 lines)
      sgnode.d.ts (126 lines)
      staticTypes.d.ts (102 lines)
    .gitattributes (14 lines)
    .gitignore (3 lines)
    .npmignore (0 lines)
    .yarnrc.yml (1 lines)
    build.rs (5 lines)
    Cargo.toml (37 lines)
    dprint.json (18 lines)
    index.d.ts (14 lines)
    index.js (411 lines)
    LICENSE (21 lines)
    package.json (81 lines)
    README.md (34 lines)
    tsconfig.json (19 lines)
  pyo3/
    ast_grep_py/
      __init__.py (85 lines)
      ast_grep_py.pyi (71 lines)
      py.typed (0 lines)
    src/
      lib.rs (65 lines)
      py_lang.rs (137 lines)
      py_node.rs (389 lines)
      range.rs (112 lines)
      unicode_position.rs (63 lines)
    tests/
      test_fix.py (52 lines)
      test_range.py (64 lines)
      test_register_lang.py (46 lines)
      test_rule.py (171 lines)
      test_simple.py (134 lines)
      test_traversal.py (131 lines)
      test_wrong_usage.py (49 lines)
    Cargo.toml (32 lines)
    pyproject.toml (45 lines)
    README.md (73 lines)
  wasm/
    __test__/
      index.spec.mjs (448 lines)
    scripts/
      patch-pkg.mjs (25 lines)
    src/
      doc.rs (255 lines)
      lib.rs (196 lines)
      sg_node.rs (409 lines)
      ts_types.rs (625 lines)
      wasm_lang.rs (254 lines)
    tests/
      setup.js (5 lines)
      web.rs (760 lines)
    Cargo.toml (33 lines)
    package.json (44 lines)
    README.md (250 lines)
npm/
  platforms/
    darwin-arm64/
      package.json (30 lines)
      README.md (3 lines)
    darwin-x64/
      package.json (30 lines)
      README.md (3 lines)
    linux-arm64-gnu/
      package.json (33 lines)
      README.md (3 lines)
    linux-x64-gnu/
      package.json (33 lines)
      README.md (3 lines)
    win32-arm64-msvc/
      package.json (30 lines)
      README.md (3 lines)
    win32-ia32-msvc/
      package.json (30 lines)
      README.md (3 lines)
    win32-x64-msvc/
      package.json (30 lines)
      README.md (3 lines)
  ast-grep (3 lines)
  package.json (44 lines)
  postinstall.js (49 lines)
  README.md (12 lines)
  sg (2 lines)
schemas/
  bash_rule.json (997 lines)
  c_rule.json (1149 lines)
  cpp_rule.json (1325 lines)
  csharp_rule.json (1307 lines)
  css_rule.json (988 lines)
  elixir_rule.json (960 lines)
  go_rule.json (1110 lines)
  haskell_rule.json (1293 lines)
  html_rule.json (898 lines)
  java_rule.json (1184 lines)
  javascript_rule.json (1126 lines)
  json_rule.json (886 lines)
  kotlin_rule.json (1134 lines)
  languages.json (3606 lines)
  lua_rule.json (974 lines)
  php_rule.json (1201 lines)
  project.json (128 lines)
  python_rule.json (1139 lines)
  ruby_rule.json (1161 lines)
  rule.json (851 lines)
  rust_rule.json (1218 lines)
  scala_rule.json (1180 lines)
  swift_rule.json (1270 lines)
  tsx_rule.json (1271 lines)
  typescript_rule.json (1255 lines)
  yaml_rule.json (935 lines)
xtask/
  src/
    main.rs (192 lines)
    schema.rs (203 lines)
  Cargo.toml (17 lines)
.editorconfig (18 lines)
.gitignore (192 lines)
.pre-commit-config.yaml (8 lines)
Cargo.toml (39 lines)
CHANGELOG.md (1820 lines)
clippy.toml (1 lines)
LICENSE (21 lines)
pyproject.toml (43 lines)
README.md (122 lines)
renovate.json (12 lines)
rust-toolchain.toml (3 lines)
rustfmt.toml (1 lines)
```
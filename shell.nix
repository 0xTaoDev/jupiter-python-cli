{
  nixpkgs ?
    import <nixpkgs> {
      config.permittedInsecurePackages = ["python-2.7.18.7"];
    },
  ...
}: let
  pkgs = nixpkgs;
  python = pkgs.python311;
in
  pkgs.mkShell {
    nativeBuildInputs = with pkgs; [
      pkg-config
      clang
      gnumake
      python
      cmake
      poetry
      gcc
      stdenv.cc.cc.lib
      python311Packages.isort
      python311Packages.black
      python311Packages.flake8
    ];

    buildInputs = with python.pkgs; [
      venvShellHook
    ];
    venvDir = "./venv";
    shellHook = ''
      export NIX_LD=${pkgs.stdenv.cc}/lib64
      export LD_LIBRARY_PATH=${pkgs.stdenv.cc.cc.lib}/lib:$LD_LIBRARY_PATH
      export PYTHONPATH=$venvDir/${python.sitePackages}:$PYTHONPATH
      poetry install
      poetry update

    '';
    postVenvCreation = ''
      unset SOURCE_DATE_EPOCH
      poetry install
      poetry update
    '';
    postShellHook = ''
      unset SOURCE_DATE_EPOCH
      export PYTHONPATH=$venvDir/${python.sitePackages}:$PYTHONPATH
    '';
  }

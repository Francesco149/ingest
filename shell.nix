{ pkgs ? import <nixpkgs> {} }:

let
  ffbins = "/tmp/ffbins";

  setup-ffbins = pkgs.writeShellScriptBin "setup-ffbins" ''
    mkdir -pv ${ffbins}
    ln -svf ${pkgs.ffmpeg}/bin/ffmpeg  ${ffbins}/ffmpeg
    ln -svf ${pkgs.ffmpeg}/bin/ffprobe ${ffbins}/ffprobe
  '';

  llama-video-py = pkgs.python312Packages.buildPythonPackage rec {
    pname = "llama_video";
    version = "0.1.3";
    pyproject = true;

    src = pkgs.fetchPypi {
      inherit pname version;
      hash = "sha256-0s1QX7y2r5+YASj/RVGVFRH1vI+FF3dUdZOAZzUigx4=";
    };

    build-system = [ pkgs.python312Packages.hatchling ];

    dependencies = with pkgs.python312Packages; [
      fastapi
      httpx
      numpy
      pillow
      pydantic
      pydantic-settings
      uvicorn
    ];

    doCheck = false;
  };

  python = pkgs.python312.withPackages (ps: with ps; [
    fastapi
    httpx
    llama-video-py
    pillow
    pytest
    sqlalchemy
    trafilatura
    uvicorn
  ]);
in

pkgs.mkShell {
  packages = with pkgs; [
    espeak-ng
    ffmpeg
    python
    setup-ffbins
    whisper-cpp
    yt-dlp
  ];

  shellHook = ''
    setup-ffbins >/dev/null
    export PATH=${ffbins}:$PATH
    echo "ingest dev shell: python $(python --version 2>&1)"
  '';
}

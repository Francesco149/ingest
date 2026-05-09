{ pkgs ? import <nixpkgs> {} }:

let
  python = pkgs.python312.withPackages (ps: with ps; [
    fastapi
    httpx
    pytest
    sqlalchemy
    trafilatura
    uvicorn
  ]);
in

pkgs.mkShell {
  packages = with pkgs; [
    ffmpeg
    python
    yt-dlp
  ];

  shellHook = ''
    echo "ingest dev shell: python $(python --version 2>&1)"
    echo "Create a local venv with: python -m venv .venv"
  '';
}

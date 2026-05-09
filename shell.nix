{ pkgs ? import <nixpkgs> {} }:

pkgs.mkShell {
  packages = with pkgs; [
    ffmpeg
    python311
    yt-dlp
  ];

  shellHook = ''
    echo "ingest dev shell: python $(python --version 2>&1)"
    echo "Create a local venv with: python -m venv .venv"
  '';
}

{
  description = "CityMind - Municipal Data Gateway with LangGraph Agent";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs =
    {
      self,
      nixpkgs,
      flake-utils,
    }:
    flake-utils.lib.eachDefaultSystem (
      system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python313;
        pythonPackages = python.pkgs;
      in
      {
        devShells.default = pkgs.mkShell {
          buildInputs = [
            python
            pythonPackages.pip
            pythonPackages.virtualenv

            # System dependencies that may be needed
            pkgs.nodejs
            pkgs.nodePackages.npm
            pkgs.gcc
            pkgs.openssl
            pkgs.zlib
          ];

          nativeBuildInputs = [ pkgs.fish ];

          shellHook = ''
            # Create venv if it doesn't exist
            if [ ! -d "venv" ]; then
              echo "Creating virtual environment..."
              python -m venv venv
            fi

            # Activate venv (bash)
            source venv/bin/activate

            # Install dependencies if requirements.txt exists
            if [ -f "requirements.txt" ]; then
              pip install -q -r requirements.txt
            fi

            echo "CityMind dev environment ready!"
            echo "Run 'cd backend && python seed.py' to seed databases"
            echo "Run 'cd backend && uvicorn main:app --reload' to start the API"
            echo "Run 'python fallback_demo.py' to run the demo"
            echo ""
            echo "For Fish shell: run 'source venv/bin/activate.fish'"
          '';

          # Environment variables
          LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
            pkgs.stdenv.cc.cc.lib
            pkgs.openssl
            pkgs.zlib
          ];
        };

        packages.default = python.pkgs.buildPythonApplication {
          pname = "citymind";
          version = "0.1.0";
          src = ./.;
          format = "other";

          propagatedBuildInputs = with pythonPackages; [
            fastapi
            uvicorn
            requests
          ];

          installPhase = ''
            mkdir -p $out/bin $out/lib/citymind
            cp -r backend agent fallback_demo.py $out/lib/citymind/

            cat > $out/bin/citymind-backend <<EOF
            #!${pkgs.bash}/bin/bash
            cd $out/lib/citymind/backend
            exec ${pythonPackages.uvicorn}/bin/uvicorn main:app "\$@"
            EOF
            chmod +x $out/bin/citymind-backend
          '';
        };
      }
    );
}

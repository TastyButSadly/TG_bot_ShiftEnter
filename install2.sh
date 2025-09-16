#!/bin/bash
set -e

# --- Логгеры ---
function yellow_log() {
  local DATE_N=$(date "+%Y-%m-%d %H:%M:%S")
  local color="\033[33m"
  echo -e "$DATE_N$color $*  \033[0m"
}

function green_log() {
  local DATE_N=$(date "+%Y-%m-%d %H:%M:%S")
  local color="\033[32m"
  echo -e "$DATE_N$color $*  \033[0m"
}

yellow_log "Please deactivate any conda environment before running this script."

UM2N_ROOT=$(pwd)
INSTALL_DIR=${UM2N_ROOT}/install
mkdir -p ${INSTALL_DIR}

# --- Firedrake ---
if [ -d ${INSTALL_DIR}/firedrake ]; then
  green_log "Firedrake already installed."
else
  yellow_log "Installing Firedrake..."
  git clone https://github.com/firedrakeproject/firedrake.git ${INSTALL_DIR}/firedrake
  python3 ${INSTALL_DIR}/firedrake/scripts/firedrake-install --minimal
  green_log "Firedrake has been installed."
fi

# Activate Firedrake environment
source ${INSTALL_DIR}/firedrake/bin/activate

# --- PyTorch ---
green_log "Installing PyTorch..."
pip install -q torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cpu

# --- PyTorch3D ---
green_log "Installing PyTorch3D..."
TORCH_VER=$(python3 -c "import torch; print(torch.__version__.split('+')[0])")
PY_VER=$(python3 -c "import sys; print(f'py{sys.version_info[0]}{sys.version_info[1]}')")

# Ссылки на готовые whl PyTorch3D (пример: py310, torch 2.3.1, cpu/cu121)
URL="https://dl.fbaipublicfiles.com/pytorch3d/packaging/wheels/${PY_VER}_cu121_pyt${TORCH_VER//./}/download.html"

if pip install -q pytorch3d -f ${URL}; then
  green_log "PyTorch3D installed from prebuilt wheel."
else
  yellow_log "No prebuilt PyTorch3D found, falling back to source build (may be slow)."
  pip install -q "git+https://github.com/facebookresearch/pytorch3d.git"
fi

# --- Movement ---
if [ -d ${VIRTUAL_ENV}/src/movement ]; then
  green_log "Movement already installed."
else
  yellow_log "Installing Movement..."
  git clone https://github.com/mesh-adaptation/movement.git ${VIRTUAL_ENV}/src/movement
  pip install -e ${VIRTUAL_ENV}/src/movement
fi

# --- UM2N ---
yellow_log "Installing UM2N..."
pip install -e ${UM2N_ROOT}

green_log "All dependencies installed successfully!"

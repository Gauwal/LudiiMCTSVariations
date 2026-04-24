#!/bin/bash
#
# Validation Script: Check Setup Before SLURM Submission
#
# Run this locally to ensure everything is configured correctly.
#
# Usage:
#   bash validate_setup.sh
#

set -e

echo "============================================================================"
echo "SLURM Sweep Setup Validation"
echo "============================================================================"
echo ""

# Check Python
echo "[1/6] Checking Python..."
if ! command -v python &> /dev/null; then
    echo "  ✗ Python not found"
    exit 1
fi
python_version=$(python --version 2>&1)
echo "  ✓ Found: $python_version"
echo ""

# Check required modules
echo "[2/6] Checking Python packages..."
required_packages=("numpy" "pandas" "matplotlib" "scipy" "joblib" "sklearn")
missing=0
for pkg in "${required_packages[@]}"; do
    if python -c "import $pkg" 2>/dev/null; then
        echo "  ✓ $pkg"
    else
        echo "  ✗ $pkg (missing - run: pip install -r requirements.txt)"
        missing=1
    fi
done
if [[ $missing -eq 1 ]]; then
    echo ""
    echo "Missing packages. Install with:"
    echo "  pip install -r slurm_sweep_full_dataset/requirements.txt"
    exit 1
fi
echo ""

# Check required directories
echo "[3/6] Checking directory structure..."
if [[ ! -d "Best_Agent_Identification_GGP" ]]; then
    echo "  ✗ Best_Agent_Identification_GGP/ not found"
    exit 1
fi
echo "  ✓ Best_Agent_Identification_GGP/"

if [[ ! -f "small_scale_warm_start.py" ]]; then
    echo "  ✗ small_scale_warm_start.py not found"
    exit 1
fi
echo "  ✓ small_scale_warm_start.py"

if [[ ! -d "outputs/training_results_luddi_raw_dataset_20260422_192655_20260422_203612" ]]; then
    echo "  ⚠ Model directory not found (warm-start will use fallback predictions)"
else
    echo "  ✓ Trained model found"
fi
echo ""

# Check scripts
echo "[4/6] Checking SLURM scripts..."
scripts=("slurm_sweep_full_dataset/main_sweep.py" 
         "slurm_sweep_full_dataset/submit_all.sh"
         "slurm_sweep_full_dataset/submit_method.sh"
         "slurm_sweep_full_dataset/aggregate_results.py")
for script in "${scripts[@]}"; do
    if [[ ! -f "$script" ]]; then
        echo "  ✗ $script not found"
        exit 1
    fi
    echo "  ✓ $script"
done
echo ""

# Quick Python test
echo "[5/6] Testing Python imports..."
python -c "
import sys
sys.path.insert(0, 'Best_Agent_Identification_GGP')
import BestAgentIdentification
import small_scale_warm_start
print('  ✓ All imports successful')
"
echo ""

# Check submit_method.sh configuration
echo "[6/6] Checking SLURM script configuration..."
if grep -q 'PROJECT_ROOT=.*HOME.*LudiiMCTSVariations' slurm_sweep_full_dataset/submit_method.sh; then
    echo "  ⚠ PROJECT_ROOT uses default path (may need adjustment for your cluster)"
    echo "    Edit: slurm_sweep_full_dataset/submit_method.sh (line ~31)"
else
    echo "  ✓ PROJECT_ROOT configured"
fi
echo ""

# Summary
echo "============================================================================"
echo "✓ VALIDATION PASSED"
echo "============================================================================"
echo ""
echo "Next steps:"
echo ""
echo "1. Edit submit_method.sh:"
echo "   PROJECT_ROOT=\"/your/actual/workspace/path\"  # Line ~31"
echo ""
echo "2. Create log directory:"
echo "   mkdir -p slurm_sweep_full_dataset/slurm_logs"
echo ""
echo "3. Submit all jobs:"
echo "   cd slurm_sweep_full_dataset"
echo "   bash submit_all.sh"
echo ""
echo "4. Or test locally first:"
echo "   python slurm_sweep_full_dataset/main_sweep.py \\"
echo "       --method baseline --time-limit 600 --seed 0 --output-dir test_out"
echo ""
echo "============================================================================"

#!/bin/bash
#
#SBATCH --job-name=mcts_T129
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results/planned_T129_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results/planned_T129_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=20G
#SBATCH --time=16:00:00

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests_combo_timevar.csv"
OUT_DIR="/home/ucl/ingi/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results"
mkdir -p "${OUT_DIR}"

echo "Running T129 on $(hostname) at $(date)"
echo "Game: Tai Shogi"
echo "Variant: Progressive History | PlayoutHS | AlphaGo | Robust"
echo "Meta: moveTime=0.2, gamesPerMatchup=100, maxMoves=2000"
echo "Estimated: cpus=5, mem=20G, time=16:00:00"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T129" --out "${OUT_DIR}/T129.csv"

echo "Job completed at $(date)"

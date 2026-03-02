#!/bin/bash
#
#SBATCH --job-name=mcts_T1737
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T1737_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T1737_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=01:14:44

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T1737 on $(hostname) at $(date)"
echo "Game: Bipartisan Y"
echo "Variant: Alpha-Beta | Random | Qualitative | Robust"
echo "Meta: moveTime=0.2, gamesPerMatchup=10, maxMoves=1000"
echo "Estimated: cpus=4, mem=7G, time=01:14:44"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1737" --out "${OUT_DIR}/T1737.csv"

echo "Job completed at $(date)"

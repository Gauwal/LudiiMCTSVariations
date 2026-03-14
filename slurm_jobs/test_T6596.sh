#!/bin/bash
#
#SBATCH --job-name=mcts_T6596
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T6596_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T6596_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=152:48:35

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T6596 on $(hostname) at $(date)"
echo "Game: The Babylonian"
echo "Variant: UCB1 | PlayoutHS | MonteCarlo | Robust"
echo "Meta: moveTime=2.0, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=4, mem=7G, time=152:48:35"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T6596" --out "${OUT_DIR}/T6596.csv"

echo "Job completed at $(date)"

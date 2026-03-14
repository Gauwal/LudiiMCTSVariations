#!/bin/bash
#
#SBATCH --job-name=mcts_T6016
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T6016_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T6016_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=152:49:09

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T6016 on $(hostname) at $(date)"
echo "Game: Currierspiel"
echo "Variant: UCB1 | PlayoutHS | MonteCarlo | Robust"
echo "Meta: moveTime=2.0, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=4, mem=8G, time=152:49:09"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T6016" --out "${OUT_DIR}/T6016.csv"

echo "Job completed at $(date)"

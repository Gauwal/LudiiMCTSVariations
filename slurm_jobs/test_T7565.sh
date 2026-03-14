#!/bin/bash
#
#SBATCH --job-name=mcts_T7565
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T7565_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T7565_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=8G
#SBATCH --time=15:19:13

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T7565 on $(hostname) at $(date)"
echo "Game: Seireigi"
echo "Variant: UCB1 | Random | MonteCarlo | MaxAvgScore"
echo "Meta: moveTime=0.2, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=4, mem=8G, time=15:19:13"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T7565" --out "${OUT_DIR}/T7565.csv"

echo "Job completed at $(date)"

#!/bin/bash
#
#SBATCH --job-name=mcts_T556
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T556_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T556_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=09:11:42

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T556 on $(hostname) at $(date)"
echo "Game: Roll-Ing to Four"
echo "Variant: McBRAVE | MAST | Implicit Minimax | Proportional Exp"
echo "Meta: moveTime=0.5, gamesPerMatchup=30, maxMoves=1000"
echo "Estimated: cpus=4, mem=7G, time=09:11:42"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T556" --out "${OUT_DIR}/T556.csv"

echo "Job completed at $(date)"

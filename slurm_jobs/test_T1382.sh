#!/bin/bash
#
#SBATCH --job-name=mcts_T1382
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T1382_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T1382_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=38G
#SBATCH --time=38:39:23

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T1382 on $(hostname) at $(date)"
echo "Game: Taikyoku Shogi"
echo "Variant: UCB1 | Random | MonteCarlo | Proportional Exp"
echo "Meta: moveTime=0.5, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=5, mem=38G, time=38:39:23"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1382" --out "${OUT_DIR}/T1382.csv"

echo "Job completed at $(date)"

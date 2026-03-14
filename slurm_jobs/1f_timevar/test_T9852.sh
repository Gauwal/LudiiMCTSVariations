#!/bin/bash
#
#SBATCH --job-name=mcts_T9852
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T9852_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T9852_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=19G
#SBATCH --time=16:00:00

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T9852 on $(hostname) at $(date)"
echo "Game: Tai Shogi"
echo "Variant: Progressive Bias | Random | MonteCarlo | Robust"
echo "Meta: moveTime=2.0, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=5, mem=19G, time=16:00:00"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T9852" --out "${OUT_DIR}/T9852.csv"

echo "Job completed at $(date)"

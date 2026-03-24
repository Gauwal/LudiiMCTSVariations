#!/bin/bash
#
#SBATCH --job-name=mcts_T1609
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T1609_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T1609_%j.err
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

PLAN="${PROJECT_DIR}/planned_tests_1f_timevar.csv"
OUT_DIR="/home/ucl/ingi/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results"
mkdir -p "${OUT_DIR}"

echo "Running T1609 on $(hostname) at $(date)"
echo "Game: Tai Shogi"
echo "Variant: UCB1 GRAVE | Random | MonteCarlo | Robust"
echo "Meta: moveTime=0.2, gamesPerMatchup=100, maxMoves=2000"
echo "Estimated: cpus=5, mem=19G, time=16:00:00"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1609" --out "${OUT_DIR}/T1609.csv"

echo "Job completed at $(date)"

#!/bin/bash
#
#SBATCH --job-name=mcts_T1787
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results/planned_T1787_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results/planned_T1787_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=4
#SBATCH --mem=7G
#SBATCH --time=16:00:00

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests_combo_timevar.csv"
OUT_DIR="/home/ucl/ingi/gsavary/LudiiMCTSVariations/slurm_jobs/combo_timevar/results"
mkdir -p "${OUT_DIR}"

echo "Running T1787 on $(hostname) at $(date)"
echo "Game: I Pere"
echo "Variant: Progressive Widening | MAST | MonteCarlo | MaxAvgScore"
echo "Meta: moveTime=1.0, gamesPerMatchup=100, maxMoves=2000"
echo "Estimated: cpus=4, mem=7G, time=16:00:00"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1787" --out "${OUT_DIR}/T1787.csv"

echo "Job completed at $(date)"

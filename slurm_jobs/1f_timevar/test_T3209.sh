#!/bin/bash
#
#SBATCH --job-name=mcts_T3209
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T3209_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T3209_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=8G
#SBATCH --time=16:00:00

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T3209 on $(hostname) at $(date)"
echo "Game: Shakhmaty (Early Modern)"
echo "Variant: Progressive History | Random | MonteCarlo | Robust"
echo "Meta: moveTime=0.2, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=5, mem=8G, time=16:00:00"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T3209" --out "${OUT_DIR}/T3209.csv"

echo "Job completed at $(date)"

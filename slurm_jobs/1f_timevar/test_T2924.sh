#!/bin/bash
#
#SBATCH --job-name=mcts_T2924
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T2924_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/1f_timevar/results/planned_T2924_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=11G
#SBATCH --time=16:00:00

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T2924 on $(hostname) at $(date)"
echo "Game: Tenjiku Shogi"
echo "Variant: ExIt | Random | MonteCarlo | Robust"
echo "Meta: moveTime=2.0, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=5, mem=11G, time=16:00:00"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T2924" --out "${OUT_DIR}/T2924.csv"

echo "Job completed at $(date)"

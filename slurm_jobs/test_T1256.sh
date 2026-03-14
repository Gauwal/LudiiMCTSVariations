#!/bin/bash
#
#SBATCH --job-name=mcts_T1256
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T1256_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T1256_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=7G
#SBATCH --time=152:49:05

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T1256 on $(hostname) at $(date)"
echo "Game: Mig Mang"
echo "Variant: UCB1 | MAST | MonteCarlo | Robust"
echo "Meta: moveTime=2.0, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=5, mem=7G, time=152:49:05"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T1256" --out "${OUT_DIR}/T1256.csv"

echo "Job completed at $(date)"

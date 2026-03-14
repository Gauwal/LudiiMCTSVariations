#!/bin/bash
#
#SBATCH --job-name=mcts_T623
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T623_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T623_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=7G
#SBATCH --time=76:24:45

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T623 on $(hostname) at $(date)"
echo "Game: Score Four"
echo "Variant: Progressive Widening | Random | MonteCarlo | Robust"
echo "Meta: moveTime=1.0, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=5, mem=7G, time=76:24:45"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T623" --out "${OUT_DIR}/T623.csv"

echo "Job completed at $(date)"

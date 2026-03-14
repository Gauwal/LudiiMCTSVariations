#!/bin/bash
#
#SBATCH --job-name=mcts_T2442
#SBATCH --output=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T2442_%j.out
#SBATCH --error=/home/users/g/s/gsavary/LudiiMCTSVariations/slurm_jobs/results/planned_T2442_%j.err
#
#SBATCH --ntasks=1
#SBATCH --cpus-per-task=5
#SBATCH --mem=8G
#SBATCH --time=38:14:27

module load Java

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
PROJECT_DIR="$HOME/LudiiMCTSVariations"
LUDII_JAR="$HOME/Ludii-1.3.14.jar"
CLASSPATH="${LUDII_JAR}:${PROJECT_DIR}/bin"

PLAN="${PROJECT_DIR}/planned_tests.csv"
OUT_DIR="${PROJECT_DIR}/out/planned_results"
mkdir -p "${OUT_DIR}"

echo "Running T2442 on $(hostname) at $(date)"
echo "Game: Shakhmaty (Early Modern)"
echo "Variant: McBRAVE | Random | MonteCarlo | Robust"
echo "Meta: moveTime=0.5, gamesPerMatchup=50, maxMoves=1000"
echo "Estimated: cpus=5, mem=8G, time=38:14:27"

srun java -cp "${CLASSPATH}" experiments.planning.RunPlannedTest --plan "${PLAN}" --test-id "T2442" --out "${OUT_DIR}/T2442.csv"

echo "Job completed at $(date)"

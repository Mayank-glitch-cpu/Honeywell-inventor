#!/bin/bash

# Colors for better readability
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
RED='\033[0;31m'
NC='\033[0m' # No Color

echo -e "${CYAN}=======================================================${NC}"
echo -e "${CYAN}     AWS IoT TwinMaker & SiteWise Master Setup         ${NC}"
echo -e "${CYAN}=======================================================${NC}"

# Function to check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check for required commands
if ! command_exists python3; then
    echo -e "${RED}Error: python3 is not installed. Please install Python 3.${NC}"
    exit 1
fi

# Set the virtual environment path
VENV_PATH="venv-sitewise"

# Step 1: Present options to the user
echo -e "\n${CYAN}Available setup options:${NC}"
echo -e "${YELLOW}1. Create TwinMaker workspace (run.sh)${NC}"
echo -e "${YELLOW}2. Create IoT SiteWise model (run-sitewise-model.sh)${NC}"
echo -e "${YELLOW}3. Create IoT SiteWise asset (run-sitewise-asset.sh)${NC}"
echo -e "${YELLOW}4. Full setup: TwinMaker + SiteWise model + asset${NC}"
echo -e "${YELLOW}5. Exit${NC}"

read -p "Select an option (1-5): " option

case $option in
    1)
        # Run TwinMaker workspace setup
        echo -e "\n${CYAN}Running TwinMaker workspace setup...${NC}"
        
        # First check if the script exists
        if [ ! -f "run.sh" ]; then
            echo -e "${RED}Error: run.sh not found!${NC}"
            exit 1
        fi
        
        # Make it executable if it isn't
        chmod +x run.sh
        
        # Run the script
        ./run.sh
        ;;
    2)
        # Run IoT SiteWise model setup
        echo -e "\n${CYAN}Running IoT SiteWise model setup...${NC}"
        
        # First check if the script exists
        if [ ! -f "run-sitewise-model.sh" ]; then
            echo -e "${RED}Error: run-sitewise-model.sh not found!${NC}"
            exit 1
        fi
        
        # Make it executable if it isn't
        chmod +x run-sitewise-model.sh
        
        # Run the script
        ./run-sitewise-model.sh
        ;;
    3)
        # Run IoT SiteWise asset setup
        echo -e "\n${CYAN}Running IoT SiteWise asset setup...${NC}"
        
        # First check if the script exists
        if [ ! -f "run-sitewise-asset.sh" ]; then
            echo -e "${RED}Error: run-sitewise-asset.sh not found!${NC}"
            exit 1
        fi
        
        # Make it executable if it isn't
        chmod +x run-sitewise-asset.sh
        
        # Run the script
        ./run-sitewise-asset.sh
        ;;
    4)
        # Full setup: TwinMaker + SiteWise model + asset
        echo -e "\n${CYAN}Running full setup sequence...${NC}"
        
        # Check if all necessary scripts exist
        for script in "run.sh" "run-sitewise-model.sh" "run-sitewise-asset.sh"; do
            if [ ! -f "$script" ]; then
                echo -e "${RED}Error: $script not found!${NC}"
                exit 1
            fi
            # Make each script executable
            chmod +x "$script"
        done
        
        # Step 1: Run TwinMaker workspace setup
        echo -e "\n${CYAN}Step 1/3: Creating TwinMaker workspace${NC}"
        echo -e "${CYAN}----------------------------------------${NC}"
        ./run.sh
        
        # Check if the previous step was successful
        if [ $? -ne 0 ]; then
            echo -e "${RED}TwinMaker workspace setup failed. Stopping the sequence.${NC}"
            exit 1
        fi
        
        # Step 2: Run IoT SiteWise model setup
        echo -e "\n${CYAN}Step 2/3: Creating IoT SiteWise model${NC}"
        echo -e "${CYAN}----------------------------------------${NC}"
        # Run the model script and capture the model ID
        model_output=$(./run-sitewise-model.sh)
        model_id=$(echo "$model_output" | grep "Model ID:" | cut -d ":" -f 2 | tr -d ' ')
        
        if [ -z "$model_id" ]; then
            echo -e "${RED}Could not determine the model ID. Please check if the model was created successfully.${NC}"
            # Ask if the user wants to continue anyway
            read -p "Do you want to continue with asset creation anyway? You'll need to provide the model ID manually (y/n): " continue_anyway
            if [[ "$continue_anyway" != "y" && "$continue_anyway" != "Y" ]]; then
                echo -e "${RED}Stopping the sequence.${NC}"
                exit 1
            fi
        else
            echo -e "${GREEN}Successfully created model with ID: ${CYAN}$model_id${NC}"
        fi
        
        # Step 3: Run IoT SiteWise asset setup
        echo -e "\n${CYAN}Step 3/3: Creating IoT SiteWise asset${NC}"
        echo -e "${CYAN}---------------------------------------${NC}"
        if [ -n "$model_id" ]; then
            # If we have the model ID, use it
            ./run-sitewise-asset.sh "$model_id"
        else
            # If not, run without parameters
            ./run-sitewise-asset.sh
        fi
        
        echo -e "\n${GREEN}Full setup sequence completed!${NC}"
        ;;
    5)
        # Exit
        echo -e "${YELLOW}Exiting. No changes were made.${NC}"
        exit 0
        ;;
    *)
        echo -e "${RED}Invalid option. Exiting.${NC}"
        exit 1
        ;;
esac

echo -e "${CYAN}=======================================================${NC}"
echo -e "${GREEN}Process completed!${NC}"
echo -e "${CYAN}=======================================================${NC}"
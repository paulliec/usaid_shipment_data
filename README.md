# 🌍 USAID Global Health Commodity Distribution Dashboard

This interactive dashboard visualizes USAID's global health commodity shipments and deliveries across multiple countries. The project provides insights into humanitarian aid distribution, medical supplies delivery, and the impact of USAID's global health initiatives.

## 📊 Features

- Interactive global map showing distribution of shipments
- Detailed metrics by country and health element
- Timeline analysis of shipment patterns
- Natural language query interface for data exploration (powered by Snowflake Cortex Analyst)
- Filterable views by year, health element, and country
- Key performance indicators and trends

## 🔧 Technical Stack

- **Frontend**: Streamlit
- **Backend**: Python
- **Database**: Snowflake Enterprise Edition
- **Natural Language Processing**: Snowflake Cortex Analyst
- **Data Analysis**: Pandas, Plotly
- **Authentication**: RSA Key-based authentication

## ⚠️ Important Note About Requirements

This project requires specific Snowflake features that are part of Snowflake Enterprise Edition:
- A Snowflake Enterprise account with Cortex Analyst enabled
- Appropriate Snowflake credits for running queries
- Proper Snowflake role permissions for database operations
- Access to Snowflake's Cortex Analyst API

If you don't have access to these Snowflake features, you have several options:
1. **Use a Local Database**: Modify the code to use a local database like SQLite or PostgreSQL (requires removing the natural language query feature)
2. **Static Data Analysis**: Use the provided CSV files directly with Pandas for analysis
3. **Contact Snowflake**: Reach out to Snowflake for a trial Enterprise account

## 🚀 Getting Started

### Prerequisites

- Python 3.8+
- Snowflake Enterprise account with:
  - Cortex Analyst enabled
  - Appropriate warehouse setup
  - Necessary database permissions
- Required Python packages (see `requirements.txt`)

### Installation

1. Clone the repository:
```bash
git clone https://github.com/[your-username]/usaid_shipment_data.git
cd usaid_shipment_data
```

2. Create and activate a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

3. Install dependencies:
```bash
pip install -r requirements.txt
```

4. Set up Snowflake:
   - Ensure you have a Snowflake Enterprise account with Cortex Analyst
   - Create necessary database and warehouse
   - Import the provided data files into Snowflake tables
   - Configure semantic layer using `HCD_Semantic_Layer.yaml`

5. Set up authentication:
   - Generate RSA key pair using the provided script:
     ```bash
     python key_value_pair.py
     ```
   - Add the public key to your Snowflake account
   - Configure `.streamlit/secrets.toml` with your Snowflake credentials (see `secrets.toml.example`)

6. Run the application:
```bash
streamlit run USAID.py
```

### Alternative Setup (Without Snowflake)

If you don't have access to Snowflake Enterprise, you can still work with the data:

1. Use the provided CSV files in the `data/` directory
2. Modify `USAID.py` to load data directly from CSV files
3. Remove or modify the natural language query feature
4. Use Pandas and Plotly directly for analysis and visualization

Example code for CSV-based setup will be provided in a future update.

## 📁 Project Structure

- `USAID.py`: Main application file containing the dashboard implementation
- `key_value_pair.py`: Utility script for RSA key generation
- `requirements.txt`: Python package dependencies
- `data/`: Directory containing the dataset files
  - `hcd.csv`: Main health commodity dataset
  - `code_lookup.csv`: Reference data for status codes
- `HCD_Semantic_Layer.yaml`: Semantic layer configuration for Snowflake

## 🔒 Security Note

This repository contains public data that was previously available on the USAID website. Sensitive credentials and keys are not included in the repository and must be configured locally.

## 📈 Data Overview

This repository includes the complete historical dataset that was previously available on the USAID website but has since been taken down. The data files are provided in the `data/` directory:

- `hcd.csv`: Complete health commodity distribution dataset
  - Contains detailed shipment records
  - Includes all historical delivery data
  - Preserves original USAID data structure
- `code_lookup.csv`: Reference data for status codes and classifications

These files are included to:
1. Allow setup of a complete Snowflake database with historical data
2. Enable analysis without Snowflake using the raw CSV files
3. Preserve this valuable public health supply chain dataset
4. Provide a reference for future health commodity distribution analysis

The dataset includes comprehensive information about:
- Global health commodity shipments
- Delivery timelines and status
- Health elements and programs
- Geographic distribution
- Shipment quantities and types
- Performance metrics and delivery status

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request. Some areas where help would be particularly appreciated:
- Adding support for alternative databases
- Creating a CSV-based version without Snowflake dependencies
- Improving visualizations and analysis
- Adding new features and insights

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 🙏 Acknowledgments

- USAID for making this data publicly available
- The global health community for their vital work
- Contributors and maintainers of the open-source tools used in this project
- Snowflake for their powerful data platform and Cortex Analyst capabilities 
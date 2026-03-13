# NIFTY Options Trading Strategy Backtester

A Python-based backtesting framework for evaluating NIFTY options trading strategies using historical market data.

The system simulates trade execution, applies strategy logic, and generates performance metrics including profit/loss and equity curves.

---

## Features

• Historical backtesting of trading strategies  
• SMA crossover strategy implementation  
• Technical indicators module  
• Market data downloader  
• Strategy performance analytics  
• Modular trading system architecture  

---

## Project Structure
data/ → historical market data
strategies/ → trading strategy implementations

backtester.py → core backtesting engine
run_backtest.py → main execution script
indicators.py → technical indicators
kite_downloader.py → Zerodha data downloader

---

## Installation

Install dependencies:

pip install -r requirements.txt

---

## Running the Backtest

Run the main backtesting script:

python run_backtest.py

---

## Tech Stack

Python  
Pandas  
NumPy  
Matplotlib  

---

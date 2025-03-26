from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import yfinance as yf
import plotly.graph_objects as go
import pandas as pd
from functools import lru_cache

app = Flask(__name__)
CORS(app)  # CORS für alle Routen aktivieren



# Globale Konfiguration
CONFIG = {
    'COLORS': {
        'Eigenkapital': '#1f77b4',  # Blau
        'Langfristige Verbindlichkeiten': '#ff7f0e',  # Orange
        'Kurzfristige Verbindlichkeiten': '#2ca02c',  # Grün
        'TICKER_COLORS': ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd']
    },
    'DEFAULT_YEARS': ['2023', '2024']
}

def get_company_info(symbols):
    return {symbol: yf.Ticker(symbol).info for symbol in symbols}

def create_company_table(symbols):
    """
    Erstellt eine Tabelle mit Unternehmensinformationen.

    Args:
        symbols (list): Liste der Ticker-Symbole.

    Returns:
        plotly.graph_objects.Figure: Die erstellte Tabelle.
    """
    data = get_company_info(symbols)
    namen = [data[symbol].get('shortName', 'N/A') for symbol in data]
    branchen = [data[symbol].get('sector', 'N/A') for symbol in data]
    länder = [data[symbol].get('country', 'N/A') for symbol in data]
    mitarbeiter = [data[symbol].get('fullTimeEmployees', 'N/A') for symbol in data]

    # Dynamische Höhe basierend auf der Anzahl der Zeilen
    row_count = len(namen)
    row_height = 50  # Höhe pro Zeile in Pixeln
    table_height = row_count * row_height + 50  # Zusätzliche Höhe für Header und Puffer

    fig = go.Figure(data=[go.Table(
        header=dict(values=['Unternehmen', 'Branche', 'Land', 'Mitarbeiter'],
                    fill_color='paleturquoise',
                    align='left'),
        cells=dict(values=[namen, branchen, länder, mitarbeiter],
                   fill_color='lavender',
                   align='left'))
    ])

    # Layout-Eigenschaften anpassen
    fig.update_layout(
        autosize=True,
        height=table_height,
        margin=dict(l=20, r=20, t=20, b=20)
    )
    return fig

def get_filtered_balance_sheet(ticker_symbol):
    """
    Holt und filtert die Bilanzdaten eines Unternehmens.

    Args:
        ticker_symbol (str): Das Ticker-Symbol.

    Returns:
        pd.DataFrame: Gefilterte Bilanzdaten.
    """
    indices = [
        'Total Non Current Assets', 'Current Assets', 'Inventory', 'Receivables',
        'Cash Cash Equivalents And Short Term Investments', 'Stockholders Equity',
        'Total Liabilities Net Minority Interest', 'Current Liabilities',
        'Total Non Current Liabilities Net Minority Interest'
    ]
    ticker = yf.Ticker(ticker_symbol)
    balance_sheet = ticker.balancesheet

    # Filtere nur die relevanten Indizes
    filtered_balance_sheet = balance_sheet.loc[indices]

    # Konvertiere die Spaltennamen in Jahreszahlen und sortiere sie
    filtered_balance_sheet.columns = filtered_balance_sheet.columns.astype(str).str[:4]
    filtered_balance_sheet = filtered_balance_sheet.sort_index(axis=1, ascending=True)

    return filtered_balance_sheet

def get_usd_to_eur_exchange_rate():
    """
    Holt den aktuellen USD/EUR-Wechselkurs.

    Returns:
        float: Der Wechselkurs.
    """
    ticker = yf.Ticker("USDEUR=X")
    exchange_rate = ticker.history(period="1d")['Close'].iloc[-1]
    return exchange_rate

def convert_dataframe_to_euro(df):
    """
    Konvertiert einen DataFrame von USD in EUR.

    Args:
        df (pd.DataFrame): Der zu konvertierende DataFrame.

    Returns:
        pd.DataFrame: Der konvertierte DataFrame.
    """
    exchange_rate = get_usd_to_eur_exchange_rate()
    df_euro = df.applymap(lambda value: value * exchange_rate)
    return df_euro

def calculate_kpis(df):
    """
    Berechnet wichtige Kennzahlen (KPIs) basierend auf Bilanzdaten.

    Args:
        df (pd.DataFrame): Der DataFrame mit Bilanzdaten.

    Returns:
        pd.DataFrame: Der DataFrame mit berechneten KPIs.
    """
    df.loc['Equity_Ratio'] = (df.loc['Stockholders Equity'] / (df.loc['Stockholders Equity'] + df.loc['Total Liabilities Net Minority Interest'])) * 100
    df.loc['Debt_Ratio'] = (df.loc['Total Liabilities Net Minority Interest'] / (df.loc['Stockholders Equity'] + df.loc['Total Liabilities Net Minority Interest'])) * 100
    df.loc['Static_Debt_Ratio'] = (df.loc['Total Liabilities Net Minority Interest'] / df.loc['Stockholders Equity']) * 100
    df.loc['Fixed_Asset_Intensity'] = df.loc['Total Non Current Assets'] / (df.loc['Current Assets'] + df.loc['Total Non Current Assets'])
    df.loc['Coverage_Ratio_1'] = df.loc['Stockholders Equity'] / df.loc['Total Non Current Assets']
    df.loc['Coverage_Ratio_2'] = (df.loc['Stockholders Equity'] + df.loc['Total Non Current Liabilities Net Minority Interest']) / df.loc['Total Non Current Assets']
    df.loc['Current_Asset_Ratio'] = df.loc['Current Assets'] / (df.loc['Current Assets'] + df.loc['Total Non Current Assets'])
    df.loc['Receivables_Ratio'] = df.loc['Receivables'] / (df.loc['Current Assets'] + df.loc['Total Non Current Assets'])
    df.loc['1. Liquidity_Ratio'] = df.loc['Current Assets'] / df.loc['Current Liabilities']
    df.loc['2. Liquidity_Ratio'] = (df.loc['Current Assets'] - df.loc['Inventory']) / df.loc['Current Liabilities']
    df.loc['3. Liquidity_Ratio'] = df.loc['Cash Cash Equivalents And Short Term Investments'] / df.loc['Current Liabilities']
    df.loc['Net_Working_Capital'] = df.loc['Current Assets'] - df.loc['Current Liabilities']
    return df

def translate_indices(df):
    """
    Übersetzt die Indizes eines DataFrames ins Deutsche.

    Args:
        df (pd.DataFrame): Der zu übersetzende DataFrame.

    Returns:
        pd.DataFrame: Der übersetzte DataFrame.
    """
    translations = {
        'Total Non Current Assets': 'Gesamtanlagevermögen',
        'Current Assets': 'Umlaufvermögen',
        'Receivables': 'Forderungen',
        'Stockholders Equity': 'Eigenkapital',
        'Total Liabilities Net Minority Interest': 'Gesamtverbindlichkeiten ohne Minderheitsanteile',
        'Current Liabilities': 'Kurzfristige Verbindlichkeiten',
        'Total Non Current Liabilities Net Minority Interest': 'Langfristige Verbindlichkeiten',
        'Equity_Ratio': 'Eigenkapitalquote',
        'Debt_Ratio': 'Fremdkapitalquote',
        'Static_Debt_Ratio': 'Statischer Verschuldungsgrad',
        'Fixed_Asset_Intensity': 'Anlageintensität',
        'Coverage_Ratio_1': 'Anlagendeckungsgrad 1',
        'Coverage_Ratio_2': 'Anlagendeckungsgrad 2',
        'Current_Asset_Ratio': 'Umlaufquote',
        'Receivables_Ratio': 'Forderungsquote',
        '1. Liquidity_Ratio': '1. Liquiditätsquote',
        '2. Liquidity_Ratio': '2. Liquiditätsquote',
        '3. Liquidity_Ratio': '3. Liquiditätsquote',
        'Net_Working_Capital': 'Netto-Umlaufvermögen'
    }
    df.rename(index=translations, inplace=True)
    return df

def clean_and_skip_nan(df):
    """
    Bereinigt den DataFrame, indem NaN-Werte beibehalten werden, sodass sie in Diagrammen übersprungen werden.

    Args:
        df (pd.DataFrame): Der zu bereinigende DataFrame.

    Returns:
        pd.DataFrame: Der bereinigte DataFrame mit beibehaltenen NaN-Werten.
    """
    df = df.apply(pd.to_numeric, errors='coerce')
    return df

@lru_cache(maxsize=128)
def get_balance_sheet(ticker_symbol):
    """
    Holt die Bilanzdaten für ein Ticker-Symbol und bereitet sie auf.

    Args:
        ticker_symbol (str): Das Ticker-Symbol.

    Returns:
        pd.DataFrame: Die aufbereiteten Bilanzdaten.
    """
    balance_sheet = get_filtered_balance_sheet(ticker_symbol)
    balance_sheet = clean_and_skip_nan(balance_sheet)
    balance_sheet_euro = convert_dataframe_to_euro(balance_sheet)
    balance_sheet_kpi = calculate_kpis(balance_sheet_euro)
    balance_sheet_german = translate_indices(balance_sheet_kpi)
    return balance_sheet_german

def is_valid_ticker(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    balance_sheet = ticker.balancesheet
    return not balance_sheet.empty

def create_structural_balance_sheet_table(ticker_symbols):
    """
    Erstellt eine Strukturbilanz-Tabelle für die angegebenen Ticker-Symbole im gewünschten HTML-Format.

    Args:
        ticker_symbols (list): Liste der Ticker-Symbole.

    Returns:
        str: HTML-Code der Strukturbilanz-Tabelle.
    """
    html_tables = ""

    for ticker in ticker_symbols:
        balance_sheet = get_balance_sheet(ticker)
        years = [col for col in balance_sheet.columns if col in ['2023', '2024']]
        if not years:
            print(f"Keine Bilanzdaten für 2023 oder 2024 für {ticker} gefunden.")
            continue

        # Überschrift für den Ticker hinzufügen
        html_tables += f"""
        <div class="ticker-title" style="font-size: 24px; font-weight: bold; margin-top: 30px; color: black;">
            Strukturbilanz für {ticker}
        </div>
        """

        for year in sorted(years, reverse=True):
            # Werte extrahieren
            anlage = balance_sheet.loc['Gesamtanlagevermögen', year]
            umlauf = balance_sheet.loc['Umlaufvermögen', year]
            summe_aktiva = anlage + umlauf

            ek = balance_sheet.loc['Eigenkapital', year]
            fk_lang = balance_sheet.loc['Langfristige Verbindlichkeiten', year]
            fk_kurz = balance_sheet.loc['Kurzfristige Verbindlichkeiten', year]
            summe_passiva = ek + fk_lang + fk_kurz

            # HTML-Tabelle erstellen
            table_html = f"""
            <style>
                .bilanz-table {{
                    border-collapse: collapse;
                    width: 100%;
                    table-layout: fixed;
                    font-family: Arial, sans-serif;
                    margin-bottom: 40px;
                }}
                .bilanz-table th, .bilanz-table td {{
                    border: 1px solid #333;
                    padding: 10px;
                    text-align: left;
                }}
                .bilanz-table th {{
                    background-color: #2b3e50;
                    color: white;
                }}
                .bilanz-table td {{
                    background-color: #1e1e1e;
                    color: white;
                }}
                .sum-row td {{
                    background-color: #333;
                    color: #ccc;
                    font-weight: bold;
                }}
                .bilanz-title {{
                    font-size: 20px;
                    font-weight: bold;
                    margin-top: 20px;
                    margin-bottom: 10px;
                    font-family: Arial, sans-serif;
                    color: white;
                }}
            </style>

            <div class="bilanz-title">Strukturbilanz von {ticker} – Jahr {year}</div>
            <table class="bilanz-table">
                <thead>
                    <tr>
                        <th>Aktiva</th>
                        <th>Wert ({year})</th>
                        <th>Passiva</th>
                        <th>Wert ({year})</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>Anlagevermögen</td>
                        <td>{anlage:,.0f} €</td>
                        <td>Eigenkapital</td>
                        <td>{ek:,.0f} €</td>
                    </tr>
                    <tr>
                        <td>Umlaufvermögen</td>
                        <td>{umlauf:,.0f} €</td>
                        <td>Langfristige Verbindlichkeiten</td>
                        <td>{fk_lang:,.0f} €</td>
                    </tr>
                    <tr>
                        <td></td>
                        <td></td>
                        <td>Kurzfristige Verbindlichkeiten</td>
                        <td>{fk_kurz:,.0f} €</td>
                    </tr>
                    <tr class="sum-row">
                        <td>Summe Aktiva</td>
                        <td>{summe_aktiva:,.0f} €</td>
                        <td>Summe Passiva</td>
                        <td>{summe_passiva:,.0f} €</td>
                    </tr>
                </tbody>
            </table>
            """
            html_tables += table_html

    return html_tables

def create_dashboard(symbols):
    """
    Erstellt ein gestapeltes Balkendiagramm für Kapital und Verbindlichkeiten der Unternehmen.

    Args:
        symbols (list): Liste der Ticker-Symbole.

    Returns:
        plotly.graph_objects.Figure: Das erstellte Balkendiagramm.
    """
    balance_sheets = {ticker: get_balance_sheet(ticker) for ticker in symbols}
    fig = go.Figure()

    # Feste Farben für die Komponenten
    colors = {
        'Eigenkapital': '#1f77b4',  # Blau
        'Langfristige Verbindlichkeiten': '#ff7f0e',  # Orange
        'Kurzfristige Verbindlichkeiten': '#2ca02c'  # Grün
    }

    # Kontrollvariablen, um die Legende nur einmal pro Komponente anzuzeigen
    show_legend = {
        'Eigenkapital': True,
        'Langfristige Verbindlichkeiten': True,
        'Kurzfristige Verbindlichkeiten': True
    }

    for ticker, balance_sheet in balance_sheets.items():
        # Berechnung der Summen für 2023 und 2024
        total_2023 = (
            balance_sheet.loc['Eigenkapital', '2023'] +
            balance_sheet.loc['Langfristige Verbindlichkeiten', '2023'] +
            balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2023']
        )
        total_2024 = (
            balance_sheet.loc['Eigenkapital', '2024'] +
            balance_sheet.loc['Langfristige Verbindlichkeiten', '2024'] +
            balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2024']
        )

        # Werte für 2023
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2023'],
            y=[balance_sheet.loc['Eigenkapital', '2023']],
            name='Eigenkapital',
            marker_color=colors['Eigenkapital'],
            showlegend=show_legend['Eigenkapital'],
            hovertemplate='Eigenkapital: %{y:,.0f} €<br>Prozentual: %{customdata:.1%}',
            customdata=[balance_sheet.loc['Eigenkapital', '2023'] / total_2023]
        ))
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2023'],
            y=[balance_sheet.loc['Langfristige Verbindlichkeiten', '2023']],
            name='Langfristige Verbindlichkeiten',
            marker_color=colors['Langfristige Verbindlichkeiten'],
            showlegend=show_legend['Langfristige Verbindlichkeiten'],
            hovertemplate='Langfristige Verbindlichkeiten: %{y:,.0f} €<br>Prozentual: %{customdata:.1%}',
            customdata=[balance_sheet.loc['Langfristige Verbindlichkeiten', '2023'] / total_2023]
        ))
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2023'],
            y=[balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2023']],
            name='Kurzfristige Verbindlichkeiten',
            marker_color=colors['Kurzfristige Verbindlichkeiten'],
            showlegend=show_legend['Kurzfristige Verbindlichkeiten'],
            hovertemplate='Kurzfristige Verbindlichkeiten: %{y:,.0f} €<br>Prozentual: %{customdata:.1%}',
            customdata=[balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2023'] / total_2023]
        ))

        # Werte für 2024
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2024'],
            y=[balance_sheet.loc['Eigenkapital', '2024']],
            name='Eigenkapital',
            marker_color=colors['Eigenkapital'],
            showlegend=False,
            hovertemplate='Eigenkapital: %{y:,.0f} €<br>Prozentual: %{customdata:.1%}',
            customdata=[balance_sheet.loc['Eigenkapital', '2024'] / total_2024]
        ))
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2024'],
            y=[balance_sheet.loc['Langfristige Verbindlichkeiten', '2024']],
            name='Langfristige Verbindlichkeiten',
            marker_color=colors['Langfristige Verbindlichkeiten'],
            showlegend=False,
            hovertemplate='Langfristige Verbindlichkeiten: %{y:,.0f} €<br>Prozentual: %{customdata:.1%}',
            customdata=[balance_sheet.loc['Langfristige Verbindlichkeiten', '2024'] / total_2024]
        ))
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2024'],
            y=[balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2024']],
            name='Kurzfristige Verbindlichkeiten',
            marker_color=colors['Kurzfristige Verbindlichkeiten'],
            showlegend=False,
            hovertemplate='Kurzfristige Verbindlichkeiten: %{y:,.0f} €<br>Prozentual: %{customdata:.1%}',
            customdata=[balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2024'] / total_2024]
        ))

        # Nach dem ersten Ticker die Legende für diese Komponenten deaktivieren
        show_legend['Eigenkapital'] = False
        show_legend['Langfristige Verbindlichkeiten'] = False
        show_legend['Kurzfristige Verbindlichkeiten'] = False

    # Layout anpassen
    fig.update_layout(
        barmode='stack',  # Gestapelte Balken
        title='Kapital und Verbindlichkeiten der Unternehmen (2023 vs 2024)',
        xaxis_title='Unternehmen und Jahr',
        yaxis_title='Betrag (€)',
        legend_title='Komponenten',
        legend=dict(
            x=1.05,  # Position der Legende außerhalb des Diagramms
            y=1,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255, 255, 255, 0.5)',
            bordercolor='black',
            borderwidth=1
        )
    )

    return fig


def create_line_chart(ticker_symbols):
    balance_sheets = {}
    fig = go.Figure()

    # Farben aus der globalen Konfiguration
    TICKER_COLORS = CONFIG['COLORS']['TICKER_COLORS']
    company_colors = {ticker: TICKER_COLORS[i] for i, ticker in enumerate(ticker_symbols)}

    # Sammle alle Jahre aus den Balance Sheets
    all_years = set()
    for ticker in ticker_symbols:
        balance_sheets[ticker] = get_balance_sheet(ticker)
        all_years.update(balance_sheets[ticker].columns)

    # Sortiere die Jahre numerisch
    sorted_years = sorted(all_years, key=lambda x: int(x))


    # Eigenkapitalquote
    for ticker, balance_sheet in balance_sheets.items():
        x_values = sorted_years
        y_values = [balance_sheet.loc['Eigenkapitalquote', year] if year in balance_sheet.columns else None for year in x_values]

        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values,
            mode='lines+markers',
            name=f'{ticker} Eigenkapitalquote',
            line=dict(color=company_colors[ticker]),
            visible=True
        ))

    # Fremdkapitalquote
    for ticker, balance_sheet in balance_sheets.items():
        x_values = sorted_years
        y_values = [balance_sheet.loc['Fremdkapitalquote', year] if year in balance_sheet.columns else None for year in x_values]

        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values,
            mode='lines+markers',
            name=f'{ticker} Fremdkapitalquote',
            line=dict(color=company_colors[ticker]),
            visible=False
        ))

    # Statischer Verschuldungsgrad
    for ticker, balance_sheet in balance_sheets.items():
        x_values = sorted_years
        y_values = [balance_sheet.loc['Fremdkapitalquote', year] if year in balance_sheet.columns else None for year in x_values]

        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values,
            mode='lines+markers',
            name=f'{ticker} Statischer Verschuldungsgrad',
            line=dict(color=company_colors[ticker]),
            visible=False
        ))

    # Layout
    fig.update_layout(
        title='Eigenkapitalquote, Fremdkapitalquote und Statischer Verschuldungsgrad',
        xaxis_title='Jahr',
        yaxis_title='Quote',
        legend_title='Unternehmen',
        updatemenus=[
            {
                'buttons': [
                    {
                        'label': 'Eigenkapitalquote',
                        'method': 'update',
                        'args': [{'visible': [True if i < len(ticker_symbols) else False for i in range(3 * len(ticker_symbols))]}]
                    },
                    {
                        'label': 'Fremdkapitalquote',
                        'method': 'update',
                        'args': [{'visible': [True if len(ticker_symbols) <= i < 2 * len(ticker_symbols) else False for i in range(3 * len(ticker_symbols))]}]
                    },
                    {
                        'label': 'Verschuldungsquote',
                        'method': 'update',
                        'args': [{'visible': [True if 2 * len(ticker_symbols) <= i < 3 * len(ticker_symbols) else False for i in range(3 * len(ticker_symbols))]}]
                    }
                ],
                'direction': 'down',
                'showactive': True
            }
        ]
    )

    return fig

def create_coverage_ratios_chart(ticker_symbols):
    balance_sheets = {}
    fig = go.Figure()

    # Farben aus der globalen Konfiguration
    TICKER_COLORS = CONFIG['COLORS']['TICKER_COLORS']
    company_colors = {ticker: TICKER_COLORS[i] for i, ticker in enumerate(ticker_symbols)}

    # Sammle alle Jahre aus den Balance Sheets
    all_years = set()
    for ticker in ticker_symbols:
        balance_sheets[ticker] = get_balance_sheet(ticker)
        all_years.update(balance_sheets[ticker].columns)

    # Sortiere die Jahre numerisch
    sorted_years = sorted(all_years, key=lambda x: int(x))

    for ticker, balance_sheet in balance_sheets.items():
        x_values = sorted_years
        y_values_coverage_1 = [balance_sheet.loc['Anlagendeckungsgrad 1', year] if year in balance_sheet.columns else None for year in x_values]
        y_values_coverage_2 = [balance_sheet.loc['Anlagendeckungsgrad 2', year] if year in balance_sheet.columns else None for year in x_values]

        # 1. Anlagendeckung
        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values_coverage_1,
            mode='lines+markers',
            name=f'{ticker} Anlagendeckungsgrad 1',
            line=dict(color=company_colors[ticker])
        ))

        # 2. Anlagendeckung
        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values_coverage_2,
            mode='lines+markers',
            name=f'{ticker} Anlagendeckungsgrad 2',
            line=dict(color=company_colors[ticker], dash='dash')
        ))

    fig.update_layout(
        title='1. und 2. Anlagendeckung im Zeitverlauf',
        xaxis_title='Jahr',
        yaxis_title='Anlagendeckungsgrad',
        legend_title='Unternehmen'
    )

    return fig

def create_liquidity_ratios_chart(ticker_symbols):
    balance_sheets = {}
    fig = go.Figure()

    # Farben aus der globalen Konfiguration
    TICKER_COLORS = CONFIG['COLORS']['TICKER_COLORS']
    company_colors = {ticker: TICKER_COLORS[i] for i, ticker in enumerate(ticker_symbols)}

    # Sammle alle Jahre aus den Balance Sheets
    all_years = set()
    for ticker in ticker_symbols:
        balance_sheets[ticker] = get_balance_sheet(ticker)
        all_years.update(balance_sheets[ticker].columns)

    # Sortiere die Jahre numerisch
    sorted_years = sorted(all_years, key=lambda x: int(x))

    for ticker, balance_sheet in balance_sheets.items():
        x_values = sorted_years
        y_values_liquidity_1 = [balance_sheet.loc['1. Liquiditätsquote', year] if year in balance_sheet.columns else None for year in x_values]
        y_values_liquidity_2 = [balance_sheet.loc['2. Liquiditätsquote', year] if year in balance_sheet.columns else None for year in x_values]
        y_values_liquidity_3 = [balance_sheet.loc['3. Liquiditätsquote', year] if year in balance_sheet.columns else None for year in x_values]

        # 1. Liquiditätsgrad
        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values_liquidity_1,
            mode='lines+markers',
            name=f'{ticker} 1. Liquiditätsgrad',
            line=dict(color=company_colors[ticker])
        ))

        # 2. Liquiditätsgrad
        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values_liquidity_2,
            mode='lines+markers',
            name=f'{ticker} 2. Liquiditätsgrad',
            line=dict(color=company_colors[ticker], dash='dash')
        ))

        # 3. Liquiditätsgrad
        fig.add_trace(go.Scatter(
            x=x_values,
            y=y_values_liquidity_3,
            mode='lines+markers',
            name=f'{ticker} 3. Liquiditätsgrad',
            line=dict(color=company_colors[ticker], dash='dot')
        ))

    fig.update_layout(
        title='1., 2. und 3. Liquiditätsgrade im Zeitverlauf',
        xaxis_title='Jahr',
        yaxis_title='Liquiditätsgrad',
        legend_title='Unternehmen'
    )

    return fig

    

def create_company_table(symbols):
    data = get_company_info(symbols)
    namen = [data[symbol].get('shortName', 'N/A') for symbol in data]
    branchen = [data[symbol].get('sector', 'N/A') for symbol in data]
    länder = [data[symbol].get('country', 'N/A') for symbol in data]
    mitarbeiter = [data[symbol].get('fullTimeEmployees', 'N/A') for symbol in data]

    # Anzahl der Zeilen berechnen
    row_count = len(namen)
    row_height = 50  # Höhe pro Zeile in Pixeln
    table_height = row_count * row_height + 50  # Zusätzliche Höhe für Header und Puffer

    fig = go.Figure(data=[go.Table(
        header=dict(values=['Unternehmen', 'Branche', 'Land', 'Mitarbeiter'],
                    fill_color='paleturquoise',
                    align='left'),
        cells=dict(values=[namen, branchen, länder, mitarbeiter],
                   fill_color='lavender',
                   align='left'))
    ])

    # Layout-Eigenschaften anpassen
    fig.update_layout(
        autosize=True,
        height=table_height,  # Dynamische Höhe basierend auf der Anzahl der Zeilen
        margin=dict(l=20, r=20, t=20, b=20)  # Ränder anpassen
    )
    return fig

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/tickers', methods=['GET'])
def get_tickers():
    query = request.args.get('q', '').upper()
    if not query:
        return jsonify([])

    try:
        tickers = yf.Ticker(query)
        # Beispiel: Rückgabe von Name und Symbol
        return jsonify([
            {"symbol": query, "name": tickers.info.get("shortName", "Unbekannt")}
        ])
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
@app.route('/update_table', methods=['POST'])
def update_table():
    symbols = request.json.get('symbols', [])
    if not symbols:
        return jsonify({"error": "Bitte geben Sie mindestens ein Ticker-Symbol ein."}), 400
    try:
        fig = create_company_table(symbols)
        return jsonify(fig.to_json())
    except Exception as e:
        print(f"Fehler beim Erstellen der Tabelle: {e}")
        return jsonify({"error": "Fehler beim Erstellen der Tabelle"}), 500

@app.route('/update_structural_balance_sheet', methods=['POST'])
def update_structural_balance_sheet():
    symbols = request.json.get('symbols', [])
    if not symbols:
        return jsonify({"error": "Keine Symbole angegeben"}), 400

    html_table = create_structural_balance_sheet_table(symbols)
    return jsonify({"html": html_table})

@app.route('/update_dashboard', methods=['POST'])
def update_dashboard():
    symbols = request.json.get('symbols', [])
    fig = create_dashboard(symbols)
    fig_json = fig.to_json()
    print("Dashboard JSON:", fig_json)  # Debugging-Ausgabe
    return jsonify(fig_json)

@app.route('/update_line_chart', methods=['POST'])
def update_line_chart():
    symbols = request.json.get('symbols', [])
    print("Erhaltene Symbole:", symbols)  # Debugging-Ausgabe

    if not symbols:
        print("Fehler: Keine Symbole erhalten.")
        return jsonify({"error": "Keine Symbole angegeben"}), 400

    fig = create_line_chart(symbols)
    if fig is None:
        print("Fehler: Die Funktion create_line_chart hat keine Figur zurückgegeben.")
        return jsonify({"error": "Fehler beim Erstellen des Diagramms"}), 500

    try:
        fig_json = fig.to_json()
        print("Line Chart JSON erfolgreich erstellt.")  # Debugging-Ausgabe
        return jsonify(fig_json)
    except Exception as e:
        print("Fehler bei der JSON-Konvertierung:", e)
        return jsonify({"error": "Fehler bei der JSON-Konvertierung"}), 500

@app.route('/update_coverage_ratios_chart', methods=['POST'])
def update_coverage_ratios_chart():
    symbols = request.json.get('symbols', [])
    if not symbols:
        return jsonify({"error": "Keine Symbole angegeben"}), 400

    fig = create_coverage_ratios_chart(symbols)
    return jsonify(fig.to_json())

@app.route('/update_liquidity_ratios_chart', methods=['POST'])
def update_liquidity_ratios_chart():
    symbols = request.json.get('symbols', [])
    if not symbols:
        return jsonify({"error": "Keine Symbole angegeben"}), 400

    fig = create_liquidity_ratios_chart(symbols)
    return jsonify(fig.to_json())

@app.route('/check_ticker', methods=['POST'])
def check_ticker():
    ticker = request.json.get('ticker', '')
    is_valid = is_valid_ticker(ticker)
    return jsonify({'is_valid': is_valid})

@app.route('/validate_ticker/<ticker>', methods=['GET'])
def validate_ticker(ticker):
    try:
        ticker_info = yf.Ticker(ticker).info
        return jsonify({"isValid": bool(ticker_info)})
    except Exception:
        return jsonify({"isValid": False})



if __name__ == '__main__':
    app.run(debug=True)
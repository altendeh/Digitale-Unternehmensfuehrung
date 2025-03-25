from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import yfinance as yf
import plotly.graph_objects as go
import random
import pandas as pd

app = Flask(__name__)
CORS(app)  # CORS für alle Routen aktivieren

def get_company_info(symbols):
    return {symbol: yf.Ticker(symbol).info for symbol in symbols}

def create_company_table(symbols):
    data = get_company_info(symbols)
    namen = [data[symbol].get('shortName', 'N/A') for symbol in data]
    branchen = [data[symbol].get('sector', 'N/A') for symbol in data]
    länder = [data[symbol].get('country', 'N/A') for symbol in data]
    mitarbeiter = [data[symbol].get('fullTimeEmployees', 'N/A') for symbol in data]

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
        height=600,  # Höhe der Tabelle anpassen
        margin=dict(l=20, r=20, t=20, b=20)  # Ränder anpassen
    )
    return fig

def get_filtered_balance_sheet(ticker_symbol):
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
    ticker = yf.Ticker("USDEUR=X")
    exchange_rate = ticker.history(period="1d")['Close'].iloc[-1]
    return exchange_rate

def convert_dataframe_to_euro(df):
    exchange_rate = get_usd_to_eur_exchange_rate()
    df_euro = df.applymap(lambda value: value * exchange_rate)
    return df_euro

def calculate_kpis(df):
    df.loc['Equity_Ratio'] = df.loc['Stockholders Equity'] / (df.loc['Stockholders Equity'] + df.loc['Total Liabilities Net Minority Interest'])
    df.loc['Debt_Ratio'] = df.loc['Total Liabilities Net Minority Interest'] / (df.loc['Stockholders Equity'] + df.loc['Total Liabilities Net Minority Interest'])
    df.loc['Static_Debt_Ratio'] = df.loc['Total Liabilities Net Minority Interest'] / df.loc['Stockholders Equity']
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

def clean_and_interpolate(df):
    """
    Bereinigt den DataFrame, indem NaN-Werte behandelt und interpoliert werden.
    - Setzt NaN-Werte in der ersten und letzten Spalte auf 0.
    - Führt eine lineare Interpolation entlang der Zeilen durch.

    Args:
        df (pd.DataFrame): Der zu bereinigende DataFrame.

    Returns:
        pd.DataFrame: Der bereinigte und interpolierte DataFrame.
    """
    # Konvertiere alle Werte in numerische Datentypen
    df = df.apply(pd.to_numeric, errors='coerce')

    # Setze NaN-Werte in der ersten und letzten Spalte auf 0
    if not df.empty:
        df.iloc[:, 0] = df.iloc[:, 0].fillna(0)  # Erste Spalte
        df.iloc[:, -1] = df.iloc[:, -1].fillna(0)  # Letzte Spalte

    # Interpolation von NaN-Werten reihenweise (entlang der Zeilen)
    df = df.interpolate(method='linear', axis=0)

    return df

def get_balance_sheet(ticker_symbol):
    balance_sheet = get_filtered_balance_sheet(ticker_symbol)
    balance_sheet = clean_and_interpolate(balance_sheet)
    balance_sheet_euro = convert_dataframe_to_euro(balance_sheet)
    balance_sheet_kpi = calculate_kpis(balance_sheet_euro)
    balance_sheet_kpi_clean = clean_and_interpolate(balance_sheet_kpi)
    balance_sheet_german = translate_indices(balance_sheet_kpi_clean)
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
    balance_sheets = {ticker: get_balance_sheet(ticker) for ticker in symbols}
    print("Balance Sheets:", balance_sheets)  # Debugging-Ausgabe
    fig = go.Figure()
    colors = {
        'Eigenkapital': 'blue',
        'Langfristige Verbindlichkeiten': 'red',
        'Kurzfristige Verbindlichkeiten': 'green'
    }
    for ticker, balance_sheet in balance_sheets.items():
        total_2023 = balance_sheet.loc['Eigenkapital', '2023'] + balance_sheet.loc['Langfristige Verbindlichkeiten', '2023'] + balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2023']
        total_2024 = balance_sheet.loc['Eigenkapital', '2024'] + balance_sheet.loc['Langfristige Verbindlichkeiten', '2024'] + balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2024']
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2023'],
            y=[balance_sheet.loc['Eigenkapital', '2023']],
            marker_color=colors['Eigenkapital'],
            hovertext=[f"{balance_sheet.loc['Eigenkapital', '2023'] / total_2023:.1%}"],
            hoverinfo='text',
            showlegend=False
        ))
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2023'],
            y=[balance_sheet.loc['Langfristige Verbindlichkeiten', '2023']],
            marker_color=colors['Langfristige Verbindlichkeiten'],
            hovertext=[f"{balance_sheet.loc['Langfristige Verbindlichkeiten', '2023'] / total_2023:.1%}"],
            hoverinfo='text',
            showlegend=False
        ))
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2023'],
            y=[balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2023']],
            marker_color=colors['Kurzfristige Verbindlichkeiten'],
            hovertext=[f"{balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2023'] / total_2023:.1%}"],
            hoverinfo='text',
            showlegend=False
        ))
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2024'],
            y=[balance_sheet.loc['Eigenkapital', '2024']],
            marker_color=colors['Eigenkapital'],
            hovertext=[f"{balance_sheet.loc['Eigenkapital', '2024'] / total_2024:.1%}"],
            hoverinfo='text',
            showlegend=False
        ))
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2024'],
            y=[balance_sheet.loc['Langfristige Verbindlichkeiten', '2024']],
            marker_color=colors['Langfristige Verbindlichkeiten'],
            hovertext=[f"{balance_sheet.loc['Langfristige Verbindlichkeiten', '2024'] / total_2024:.1%}"],
            hoverinfo='text',
            showlegend=False
        ))
        fig.add_trace(go.Bar(
            x=[f'{ticker} 2024'],
            y=[balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2024']],
            marker_color=colors['Kurzfristige Verbindlichkeiten'],
            hovertext=[f"{balance_sheet.loc['Kurzfristige Verbindlichkeiten', '2024'] / total_2024:.1%}"],
            hoverinfo='text',
            showlegend=False
        ))
    fig.add_trace(go.Bar(
        x=[None],
        y=[None],
        name='Eigenkapital',
        marker_color=colors['Eigenkapital']
    ))
    fig.add_trace(go.Bar(
        x=[None],
        y=[None],
        name='Langfristige Verbindlichkeiten',
        marker_color=colors['Langfristige Verbindlichkeiten']
    ))
    fig.add_trace(go.Bar(
        x=[None],
        y=[None],
        name='Kurzfristige Verbindlichkeiten',
        marker_color=colors['Kurzfristige Verbindlichkeiten']
    ))

    fig.update_layout(
        barmode='stack',
        title='Kapital und Verbindlichkeiten der Unternehmen (2023 vs 2024)',
        xaxis_title='Unternehmen und Jahr',
        yaxis_title='Betrag',
        legend_title='Komponenten',
        xaxis=dict(
            tickmode='array',
            tickvals=[f'{ticker} 2023' for ticker in symbols] + [f'{ticker} 2024' for ticker in symbols],
            ticktext=[f'2023\n{ticker}' for ticker in symbols] + [f'2024\n{ticker}' for ticker in symbols]
        )
    )

    return fig

def generate_random_color():
    return "#{:06x}".format(random.randint(0, 0xFFFFFF))

def create_line_chart(ticker_symbols):
    balance_sheets = {}
    fig = go.Figure()

    # Farben für die Unternehmen festlegen
    company_colors = {ticker: generate_random_color() for ticker in ticker_symbols}

    # Erstellen eines Dashboards für gegebene Unternehmen
    for ticker in ticker_symbols:
        balance_sheets[f'{ticker}'] = get_balance_sheet(ticker)

    # Hinzufügen der Liniendiagramm-Daten für die Eigenkapitalquote
    for ticker, balance_sheet in balance_sheets.items():
        # Debugging-Ausgabe für Eigenkapitalquote
        print(f"Ticker: {ticker}, Eigenkapitalquote (vorher): {balance_sheet.loc['Eigenkapitalquote'].values}")

        x_values = balance_sheet.columns
        y_values = balance_sheet.loc['Eigenkapitalquote', x_values]

        # Debugging-Ausgabe für x_values und y_values
        print(f"Ticker: {ticker}, x-Werte (Jahre): {x_values}")
        print(f"Ticker: {ticker}, y-Werte (Eigenkapitalquote): {y_values.values}")

        fig.add_trace(go.Scatter(
            x=x_values.tolist(),
            y=y_values.tolist(),
            mode='lines+markers',
            name=f'{ticker} Eigenkapitalquote',
            line=dict(color=company_colors[ticker]),
            visible=True
        ))

    # Hinzufügen der Liniendiagramm-Daten für die Fremdkapitalquote
    for ticker, balance_sheet in balance_sheets.items():
        # Debugging-Ausgabe für Fremdkapitalquote
        print(f"Ticker: {ticker}, Fremdkapitalquote (vorher): {balance_sheet.loc['Fremdkapitalquote'].values}")

        x_values = balance_sheet.columns
        y_values = balance_sheet.loc['Fremdkapitalquote', x_values]

        # Debugging-Ausgabe für x_values und y_values
        print(f"Ticker: {ticker}, x-Werte (Jahre): {x_values}")
        print(f"Ticker: {ticker}, y-Werte (Fremdkapitalquote): {y_values.values}")

        fig.add_trace(go.Scatter(
            x=x_values.tolist(),
            y=y_values.tolist(),
            mode='lines+markers',
            name=f'{ticker} Fremdkapitalquote',
            line=dict(color=company_colors[ticker]),
            visible=False
        ))

    # Hinzufügen der Liniendiagramm-Daten für den statischen Verschuldungsgrad
    for ticker, balance_sheet in balance_sheets.items():
        # Debugging-Ausgabe für Statischer Verschuldungsgrad
        print(f"Ticker: {ticker}, Statischer Verschuldungsgrad (vorher): {balance_sheet.loc['Statischer Verschuldungsgrad'].values}")

        x_values = balance_sheet.columns
        y_values = balance_sheet.loc['Statischer Verschuldungsgrad', x_values]

        # Debugging-Ausgabe für x_values und y_values
        print(f"Ticker: {ticker}, x-Werte (Jahre): {x_values}")
        print(f"Ticker: {ticker}, y-Werte (Statischer Verschuldungsgrad): {y_values.values}")

        fig.add_trace(go.Scatter(
            x=x_values.tolist(),
            y=y_values.tolist(),
            mode='lines+markers',
            name=f'{ticker} Statischer Verschuldungsgrad',
            line=dict(color=company_colors[ticker]),
            visible=False,
            connectgaps=True  # Lücken ignorieren und verbinden
        ))
    # Layout anpassen für das interaktive Diagramm
    fig.update_layout(
        title='Eigenkapitalquote, Fremdkapitalquote und Statischer Verschuldungsgrad',
        xaxis_title='Jahr',
        yaxis_title='Quote',
        legend_title='Unternehmen',
        legend=dict(
            x=1,
            y=1,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255, 255, 255, 0.5)',
            bordercolor='black',
            borderwidth=1
        ),
        updatemenus=[
            {
                'buttons': [
                    {
                        'label': 'Eigenkapitalquote',
                        'method': 'update',
                        'args': [
                            {'visible': [True if i < len(ticker_symbols) else False for i in range(3 * len(ticker_symbols))]},
                            {'title': 'Eigenkapitalquote'}
                        ]
                    },
                    {
                        'label': 'Fremdkapitalquote',
                        'method': 'update',
                        'args': [
                            {'visible': [True if len(ticker_symbols) <= i < 2 * len(ticker_symbols) else False for i in range(3 * len(ticker_symbols))]},
                            {'title': 'Fremdkapitalquote'}
                        ]
                    },
                    {
                        'label': 'Verschuldungsquote',
                        'method': 'update',
                        'args': [
                            {'visible': [True if 2 * len(ticker_symbols) <= i < 3 * len(ticker_symbols) else False for i in range(3 * len(ticker_symbols))]},
                            {'title': 'Verschuldungsquote'}
                        ]
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

    # Farben für die Unternehmen festlegen
    company_colors = {ticker: generate_random_color() for ticker in ticker_symbols}

    for ticker in ticker_symbols:
        balance_sheets[ticker] = get_balance_sheet(ticker)

    # Hinzufügen der Liniendiagramm-Daten für die 1. und 2. Anlagendeckung
    for ticker, balance_sheet in balance_sheets.items():
        x_values = balance_sheet.columns

        # 1. Anlagendeckung
        y_values_coverage_1 = balance_sheet.loc['Anlagendeckungsgrad 1', x_values]
        fig.add_trace(go.Scatter(
            x=x_values.tolist(),
            y=y_values_coverage_1.tolist(),
            mode='lines+markers',
            name=f'{ticker} Anlagendeckungsgrad 1',
            line=dict(color=company_colors[ticker])
        ))

        # 2. Anlagendeckung
        y_values_coverage_2 = balance_sheet.loc['Anlagendeckungsgrad 2', x_values]
        fig.add_trace(go.Scatter(
            x=x_values.tolist(),
            y=y_values_coverage_2.tolist(),
            mode='lines+markers',
            name=f'{ticker} Anlagendeckungsgrad 2',
            line=dict(color=company_colors[ticker], dash='dash')  # Gepunktete Linie für 2. Anlagendeckung
        ))

    # Layout anpassen
    fig.update_layout(
        title='1. und 2. Anlagendeckung im Zeitverlauf',
        xaxis_title='Jahr',
        yaxis_title='Anlagendeckungsgrad',
        legend_title='Unternehmen',
        legend=dict(
            x=1,
            y=1,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255, 255, 255, 0.5)',
            bordercolor='black',
            borderwidth=1
        )
    )

    return fig

def create_liquidity_ratios_chart(ticker_symbols):
    balance_sheets = {}
    fig = go.Figure()

    # Farben für die Unternehmen festlegen
    company_colors = {ticker: generate_random_color() for ticker in ticker_symbols}

    for ticker in ticker_symbols:
        balance_sheets[ticker] = get_balance_sheet(ticker)

    # Hinzufügen der Liniendiagramm-Daten für die 1., 2. und 3. Liquiditätsgrade
    for ticker, balance_sheet in balance_sheets.items():
        x_values = balance_sheet.columns

        # 1. Liquiditätsgrad
        y_values_liquidity_1 = balance_sheet.loc['1. Liquiditätsquote', x_values]
        fig.add_trace(go.Scatter(
            x=x_values.tolist(),
            y=y_values_liquidity_1.tolist(),
            mode='lines+markers',
            name=f'{ticker} 1. Liquiditätsgrad',
            line=dict(color=company_colors[ticker])
        ))

        # 2. Liquiditätsgrad
        y_values_liquidity_2 = balance_sheet.loc['2. Liquiditätsquote', x_values]
        fig.add_trace(go.Scatter(
            x=x_values.tolist(),
            y=y_values_liquidity_2.tolist(),
            mode='lines+markers',
            name=f'{ticker} 2. Liquiditätsgrad',
            line=dict(color=company_colors[ticker], dash='dash')  # Gepunktete Linie für 2. Liquiditätsgrad
        ))

        # 3. Liquiditätsgrad
        y_values_liquidity_3 = balance_sheet.loc['3. Liquiditätsquote', x_values]
        fig.add_trace(go.Scatter(
            x=x_values.tolist(),
            y=y_values_liquidity_3.tolist(),
            mode='lines+markers',
            name=f'{ticker} 3. Liquiditätsgrad',
            line=dict(color=company_colors[ticker], dash='dot')  # Gepunktete Linie für 3. Liquiditätsgrad
        ))

    # Layout anpassen
    fig.update_layout(
        title='1., 2. und 3. Liquiditätsgrade im Zeitverlauf',
        xaxis_title='Jahr',
        yaxis_title='Liquiditätsgrad',
        legend_title='Unternehmen',
        legend=dict(
            x=1,
            y=1,
            xanchor='left',
            yanchor='top',
            bgcolor='rgba(255, 255, 255, 0.5)',
            bordercolor='black',
            borderwidth=1
        )
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

@app.route('/update_table', methods=['POST'])
def update_table():
    symbols = request.json.get('symbols', [])
    fig = create_company_table(symbols)
    fig_json = fig.to_json()
    print("Table JSON:", fig_json)  # Debugging-Ausgabe
    return jsonify(fig_json)

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



if __name__ == '__main__':
    app.run(debug=True)
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
import yfinance as yf
import plotly.graph_objects as go
import random

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
    filtered_balance_sheet = balance_sheet.loc[indices]
    filtered_balance_sheet.columns = filtered_balance_sheet.columns.astype(str).str[:4]
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
    df.loc['Current_Asset_Ratio'] = df.loc['Current Assets'] / (df.loc['Current Assets'] + df.loc['Total Non Current Assets'])
    df.loc['Receivables_Ratio'] = df.loc['Receivables'] / (df.loc['Current Assets'] + df.loc['Total Non Current Assets'])
    df.loc['1. Liquidity_Ratio'] = df.loc['Current Assets'] / df.loc['Current Liabilities']
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
        'Debt_Ratio': 'Verschuldungsquote',
        'Static_Debt_Ratio': 'Statischer Verschuldungsgrad',
        'Fixed_Asset_Intensity': 'Anlageintensität',
        'Current_Asset_Ratio': 'Umlaufquote',
        'Receivables_Ratio': 'Forderungsquote',
        '1. Liquidity_Ratio': '1. Liquiditätsquote',
        'Net_Working_Capital': 'Netto-Umlaufvermögen'
    }
    df.rename(index=translations, inplace=True)
    return df

def get_balance_sheet(ticker_symbol):
    balance_sheet = get_filtered_balance_sheet(ticker_symbol)
    balance_sheet_euro = convert_dataframe_to_euro(balance_sheet)
    balance_sheet_kpi = calculate_kpis(balance_sheet_euro)
    balance_sheet_german = translate_indices(balance_sheet_kpi)
    return balance_sheet_german

def is_valid_ticker(ticker_symbol):
    ticker = yf.Ticker(ticker_symbol)
    balance_sheet = ticker.balancesheet
    return not balance_sheet.empty

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
        # Spalten umsortieren
        balance_sheet = balance_sheet.sort_index(axis=1, ascending=True)
        fig.add_trace(go.Scatter(
            x=balance_sheet.columns,
            y=balance_sheet.loc['Eigenkapitalquote'],
            mode='lines+markers',
            name=f'{ticker} Eigenkapitalquote',
            line=dict(color=company_colors[ticker]),
            visible=True
        ))

    # Hinzufügen der Liniendiagramm-Daten für die Verschuldungsquote
    for ticker, balance_sheet in balance_sheets.items():
        fig.add_trace(go.Scatter(
            x=balance_sheet.columns,
            y=balance_sheet.loc['Verschuldungsquote'],
            mode='lines+markers',
            name=f'{ticker} Verschuldungsquote',
            line=dict(color=company_colors[ticker]),
            visible=False
        ))

    # Layout anpassen für das interaktive Diagramm
    fig.update_layout(
        title='Eigenkapitalquote und Verschuldungsquote',
        xaxis_title='Jahr',
        yaxis_title='Quote',
        legend_title='Unternehmen',
        updatemenus=[
            {
                'buttons': [
                    {
                        'label': 'Eigenkapitalquote',
                        'method': 'update',
                        'args': [{'visible': [True if i < len(ticker_symbols) else False for i in range(2 * len(ticker_symbols))]},
                                {'title': 'Eigenkapitalquote'}]
                    },
                    {
                        'label': 'Verschuldungsquote',
                        'method': 'update',
                        'args': [{'visible': [False if i < len(ticker_symbols) else True for i in range(2 * len(ticker_symbols))]},
                                {'title': 'Verschuldungsquote'}]
                    }
                ],
                'direction': 'down',
                'showactive': True
            }
        ]
    )

    return fig

def create_additional_chart(symbols):
    balance_sheets = {ticker: get_balance_sheet(ticker) for ticker in symbols}
    fig = go.Figure()
    kpis = [
        'Eigenkapitalquote', 'Verschuldungsquote', '1. Liquiditätsquote', 'Netto-Umlaufvermögen'
    ]
    
    # Farben für die KPIs festlegen
    kpi_colors = {
        'Eigenkapitalquote': 'blue',
        'Verschuldungsquote': 'red',
        '1. Liquiditätsquote': 'green',
        'Netto-Umlaufvermögen': 'orange'
    }

    for ticker, balance_sheet in balance_sheets.items():
        for kpi in kpis:
            fig.add_trace(go.Bar(
                x=[f'{ticker}'],
                y=[balance_sheet.loc[kpi].values[0]],  # Nur den ersten Wert verwenden (2023)
                name=f'{ticker} {kpi}',
                marker_color=kpi_colors[kpi],
                hovertext=[f"{balance_sheet.loc[kpi].values[0]:.2f}"],
                hoverinfo='text',
                showlegend=True
            ))

    # Layout des Diagramms anpassen
    fig.update_layout(
        barmode='group',
        title='Wichtige KPIs der Unternehmen',
        xaxis_title='Unternehmen',
        yaxis_title='Wert',
        legend_title='Kennzahlen',
        xaxis=dict(
            tickmode='array',
            tickvals=[f'{ticker}' for ticker in symbols],
            ticktext=[f'{ticker}' for ticker in symbols]
        )
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
    fig = create_line_chart(symbols)
    if fig is None:
        print("Fehler: Die Figur ist None")
    else:
        fig_json = fig.to_json()
        print("Line Chart JSON:", fig_json)  # Debugging-Ausgabe
        return jsonify(fig_json)

@app.route('/check_ticker', methods=['POST'])
def check_ticker():
    ticker = request.json.get('ticker', '')
    is_valid = is_valid_ticker(ticker)
    return jsonify({'is_valid': is_valid})

@app.route('/update_additional_chart', methods=['POST'])
def update_additional_chart():
    symbols = request.json.get('symbols', [])
    fig = create_additional_chart(symbols)
    fig_json = fig.to_json()
    print("Additional Chart JSON:", fig_json)  # Debugging
    return jsonify(fig_json)

if __name__ == '__main__':
    app.run(debug=True)
let tickers = [];

// Funktion zum Hinzufügen eines Tickers
async function addTicker() {
    const input = document.getElementById('ticker-input');
    const ticker = input.value.trim().toUpperCase();
    const errorMessage = document.getElementById('error-message');
    errorMessage.textContent = '';

    // Überprüfen, ob die maximale Anzahl von Tickern erreicht wurde
    if (tickers.length >= 5) {
        errorMessage.textContent = 'Sie können maximal 5 Ticker gleichzeitig auswählen.';
        return;
    }

    if (ticker && !tickers.includes(ticker)) {
        const isValid = await checkTickerValidity(ticker);
        if (isValid) {
            tickers.push(ticker);
            updateTickerList();
            input.value = '';
        } else {
            errorMessage.textContent = 'Ungültiges Tickersymbol. Bitte versuchen Sie es erneut.';
        }
    } else if (tickers.includes(ticker)) {
        errorMessage.textContent = 'Dieser Ticker wurde bereits hinzugefügt.';
    }
}

// Funktion zur Überprüfung der Ticker-Gültigkeit
async function checkTickerValidity(ticker) {
    const response = await fetch('/check_ticker', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ ticker })
    });
    const data = await response.json();
    return data.is_valid;
}

// Funktion zum Entfernen eines Tickers
function removeTicker(ticker) {
    tickers = tickers.filter(t => t !== ticker);
    updateTickerList();
}

// Funktion zum Aktualisieren der Ticker-Liste
function updateTickerList() {
    const list = document.getElementById('ticker-list');
    list.innerHTML = '';
    tickers.forEach(ticker => {
        const li = document.createElement('li');
        li.innerHTML = `${ticker} <button onclick="removeTicker('${ticker}')">Löschen</button>`;
        list.appendChild(li);
    });
}

// Event-Listener für die Enter-Taste
document.getElementById('ticker-input').addEventListener('keydown', function (event) {
    if (event.key === 'Enter') {
        addTicker();
    }
});

// Funktion zum Erstellen des Dashboards
async function createDashboard() {
    const tableContainer = document.getElementById('table-container');
    tableContainer.innerHTML = '';

    // Tabelle erstellen
    const response = await fetch('/update_table', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ symbols: tickers })
    });
    const fig = await response.json();
    const figData = JSON.parse(fig);
    Plotly.newPlot('table-container', figData.data, figData.layout, { responsive: true });
    document.getElementById('table-title').classList.remove('hidden');
    document.getElementById('table-description').classList.remove('hidden');

    // Strukturbilanz-Tabelle erstellen
    const structuralBalanceSheetResponse = await fetch('/update_structural_balance_sheet', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ symbols: tickers })
    });
    const structuralBalanceSheetData = await structuralBalanceSheetResponse.json();
    if (structuralBalanceSheetData.html) {
        document.getElementById('structural-balance-sheet-container').innerHTML = structuralBalanceSheetData.html;
        document.getElementById('structural-balance-sheet-title').classList.remove('hidden');
        document.getElementById('structural-balance-sheet-description').classList.remove('hidden');
    } else {
        console.error("Fehler beim Laden der Strukturbilanz-Tabelle:", structuralBalanceSheetData.error);
    }

    // Dashboard erstellen
    const dashboardResponse = await fetch('/update_dashboard', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ symbols: tickers })
    });
    const dashboardFig = await dashboardResponse.json();
    const dashboardFigData = JSON.parse(dashboardFig);
    Plotly.newPlot('dashboard-container', dashboardFigData.data, dashboardFigData.layout, { responsive: true });
    document.getElementById('dashboard-title').classList.remove('hidden');
    document.getElementById('dashboard-description').classList.remove('hidden');

    // Liniendiagramm erstellen
    const lineChartResponse = await fetch('/update_line_chart', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ symbols: tickers })
    });
    const lineChartFig = await lineChartResponse.json();
    const lineChartFigData = JSON.parse(lineChartFig);
    Plotly.newPlot('line-chart-container', lineChartFigData.data, lineChartFigData.layout, { responsive: true });
    document.getElementById('line-chart-title').classList.remove('hidden');
    document.getElementById('line-chart-description').classList.remove('hidden');

    // Anlagendeckungsgrade erstellen
    const coverageRatiosResponse = await fetch('/update_coverage_ratios_chart', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ symbols: tickers })
    });
    const coverageRatiosFig = await coverageRatiosResponse.json();
    const coverageRatiosFigData = JSON.parse(coverageRatiosFig);
    Plotly.newPlot('coverage-ratios-container', coverageRatiosFigData.data, coverageRatiosFigData.layout, { responsive: true });
    document.getElementById('coverage-ratios-title').classList.remove('hidden');
    document.getElementById('coverage-ratios-description').classList.remove('hidden');

    // Liquiditätsgrade erstellen
    const liquidityRatiosResponse = await fetch('/update_liquidity_ratios_chart', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({ symbols: tickers })
    });
    const liquidityRatiosFig = await liquidityRatiosResponse.json();
    const liquidityRatiosFigData = JSON.parse(liquidityRatiosFig);
    Plotly.newPlot('liquidity-ratios-container', liquidityRatiosFigData.data, liquidityRatiosFigData.layout, { responsive: true });
    document.getElementById('liquidity-ratios-title').classList.remove('hidden');
    document.getElementById('liquidity-ratios-description').classList.remove('hidden');
}

function saveDashboard() {
    const dashboardName = prompt("Bitte geben Sie einen Namen für das Dashboard ein:");
    if (!dashboardName) {
        alert("Das Dashboard wurde nicht gespeichert, da kein Name angegeben wurde.");
        return;
    }

    const dashboardData = {
        name: dashboardName,
        tickers: tickers, // Aktuelle Ticker-Liste
        timestamp: new Date().toISOString() // Zeitstempel
    };

    // Lade bestehende Dashboards aus LocalStorage
    const savedDashboards = JSON.parse(localStorage.getItem("dashboards")) || [];
    savedDashboards.push(dashboardData);

    // Speichere die aktualisierte Liste der Dashboards in LocalStorage
    localStorage.setItem("dashboards", JSON.stringify(savedDashboards));

    // Aktualisiere die Anzeige der gespeicherten Dashboards
    displaySavedDashboards();

    alert(`Dashboard "${dashboardName}" wurde erfolgreich gespeichert.`);
}

function loadDashboardByIndex(index) {
    const savedDashboards = JSON.parse(localStorage.getItem("dashboards")) || [];
    const selectedDashboard = savedDashboards[index];
    tickers = selectedDashboard.tickers; // Lade die Ticker-Liste
    updateTickerList(); // Aktualisiere die Anzeige der Ticker-Liste
    createDashboard(); // Erstelle das Dashboard basierend auf den geladenen Tickern
    alert(`Dashboard "${selectedDashboard.name}" wurde erfolgreich geladen.`);
}

function deleteDashboard(index) {
    const savedDashboards = JSON.parse(localStorage.getItem("dashboards")) || [];
    const deletedDashboard = savedDashboards.splice(index, 1);
    localStorage.setItem("dashboards", JSON.stringify(savedDashboards));
    alert(`Dashboard "${deletedDashboard[0].name}" wurde erfolgreich gelöscht.`);
    displaySavedDashboards(); // Aktualisiere die Liste der gespeicherten Dashboards
}

// Event-Listener, um gespeicherte Dashboards nach dem Laden der Seite anzuzeigen
document.addEventListener("DOMContentLoaded", () => {
    displaySavedDashboards();
});

function displaySavedDashboards() {
    const savedDashboards = JSON.parse(localStorage.getItem("dashboards")) || [];
    const dashboardList = document.getElementById("saved-dashboards-list");
    dashboardList.innerHTML = ""; // Liste zurücksetzen

    savedDashboards.forEach((dashboard, index) => {
        const li = document.createElement("li");
        li.innerHTML = `
            <span>${dashboard.name}</span>
            <div>
                <button onclick="loadDashboardByIndex(${index})">Laden</button>
                <button onclick="deleteDashboard(${index})" style="color: red;">Löschen</button>
            </div>
        `;
        dashboardList.appendChild(li);
    });
}

async function suggestTickers() {
    const input = document.getElementById("ticker-input").value.toUpperCase();
    const suggestionsList = document.getElementById("ticker-suggestions");

    // Leere die Vorschläge, wenn das Eingabefeld leer ist
    if (!input) {
        suggestionsList.innerHTML = "";
        return;
    }

    try {
        // Beispiel-API-Aufruf (ersetze durch eine echte API)
        const response = await fetch(`https://query2.finance.yahoo.com/v1/finance/search?q=${input}`);
        const data = await response.json();

        // Leere die Vorschläge
        suggestionsList.innerHTML = "";

        // Füge die gefilterten Vorschläge hinzu
        data.forEach(ticker => {
            const li = document.createElement("li");
            li.textContent = ticker.symbol; // Beispiel: ticker.symbol
            li.onclick = () => selectTicker(ticker.symbol);
            suggestionsList.appendChild(li);
        });
    } catch (error) {
        console.error("Fehler beim Abrufen der Tickersymbole:", error);
    }
}
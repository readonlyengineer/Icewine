// Developer check: real Qt Widgets consumes Icewine's per-process stylesheet.
#include <QApplication>
#include <QFile>
#include <QJsonDocument>
#include <QJsonObject>
#include <QListView>
#include <QProxyStyle>
#include <QRegularExpression>
#include <cstdio>

int main(int argc, char** argv) {
    QApplication app(argc, argv);
    if (argc != 2) return 1;
    // PCManFM-Qt installs its own proxy over the selected Qt style.
    app.setStyle(new QProxyStyle());
    const QString current = QString::fromLocal8Bit(argv[1]);
    QFile paletteFile(current + "/palette.json"), kittyFile(current + "/kitty.conf"), qssFile(current + "/pcmanfm-qt.qss");
    if (!paletteFile.open(QIODevice::ReadOnly) || !kittyFile.open(QIODevice::ReadOnly)
        || !qssFile.open(QIODevice::ReadOnly)) return 1;
    const auto palette = QJsonDocument::fromJson(paletteFile.readAll()).object();
    const auto background = QRegularExpression("^background #([0-9a-f]{6})$", QRegularExpression::MultilineOption)
        .match(QString::fromUtf8(kittyFile.readAll())).captured(1);
    const auto selectionText = QRegularExpression("selection-color: #([0-9a-f]{6});")
        .match(QString::fromUtf8(qssFile.readAll())).captured(1);
    QListView view;
    view.ensurePolished();
    const auto colors = view.palette();
    if (background.isEmpty()
        || colors.color(QPalette::Base) != QColor("#" + background)
        || colors.color(QPalette::Text) != QColor("#" + palette["foreground"].toString())
        || colors.color(QPalette::Highlight) != QColor("#" + palette["selection"].toString())
        || selectionText.isEmpty() || colors.color(QPalette::HighlightedText) != QColor("#" + selectionText)) return 1;
    std::puts("PASS: Qt Widgets per-process PCManFM palette matches terminal and selection");
}

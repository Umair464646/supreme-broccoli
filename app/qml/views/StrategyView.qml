import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

Item {
    anchors.fill: parent

    ColumnLayout {
        anchors.fill: parent
        anchors.margins: 10
        spacing: 10

        RowLayout {
            Layout.fillWidth: true
            TextField { id: search; placeholderText: "Search strategy name / id"; Layout.fillWidth: true }
            ComboBox { id: familyFilter; model: ["all", "trend", "breakout", "reversal", "flow_confirmed"] }
        }

        ScrollView {
            Layout.fillWidth: true
            Layout.fillHeight: true

            Column {
                width: parent.width
                spacing: 8
                Repeater {
                    model: appState.strategies
                    delegate: StrategyItem {
                        required property var modelData
                        required property int index
                        width: parent.width
                        row: modelData
                        visible: {
                            var q = search.text.toLowerCase()
                            var passSearch = q.length === 0 || modelData.name.toLowerCase().indexOf(q) >= 0 || modelData.id.toLowerCase().indexOf(q) >= 0
                            var passFamily = familyFilter.currentText === "all" || modelData.family === familyFilter.currentText
                            return passSearch && passFamily
                        }
                        selected: appState.selectedStrategy && appState.selectedStrategy.id === modelData.id
                        onClicked: appState.selectStrategy(index)
                    }
                }
            }
        }
    }
}

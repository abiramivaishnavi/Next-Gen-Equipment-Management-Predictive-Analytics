import EntityPage from "../components/EntityPage";

const fuelRatesConfig = {
    title: "Fuel Rates",
    endpoint: "/fuel-rates/",
    idField: "Fuel_Rate_ID",
    columns: [
        { name: "Fuel_Rate_ID", label: "Rate ID", editable: false },
        { name: "Fuel_Type", label: "Fuel Type", type: "text", required: true },
        { name: "Rate_Per_Liter", label: "Rate per Liter (SAR)", type: "number", required: true },
        { name: "Effective_Date", label: "Effective Date", type: "date", required: true },
    ],
};

function FuelRatesPage() {
    return <EntityPage config={fuelRatesConfig} />;
}

export default FuelRatesPage;
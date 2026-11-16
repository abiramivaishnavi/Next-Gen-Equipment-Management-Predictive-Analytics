import TransferQueue from "../components/TransferQueue";

/** Fleet Manager: review requests, see the full picture, approve or reject. Approver = the logged-in user. */
function TransferApprovalsPage() {
    return (
        <div className="card-panel">
            <div className="card-head">
                <div>
                    <h3 className="card-title">Transfer queue</h3>
                    <div className="card-sub">Approve or reject right in the list. Click a row for equipment condition and project details.</div>
                </div>
            </div>
            <TransferQueue mode="approve" initialTab="Pending" />
        </div>
    );
}

export default TransferApprovalsPage;

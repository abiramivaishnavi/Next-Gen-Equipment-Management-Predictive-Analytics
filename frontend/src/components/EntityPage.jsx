import { useState, useEffect, useRef } from "react";
import { Link } from "react-router-dom";
import apiClient from "../api/client";
import { applyOverrides, fuelUnit } from "./entityOverrides";

const LATEST_COUNT = 10; // register pages only show the latest few entries; the Records page has the rest

function formatApiError(err) {
    const detail = err.response?.data?.detail;
    if (typeof detail === "string") return detail;
    if (Array.isArray(detail)) {
        return detail
            .map((d) => `${d.loc?.slice(-1)[0] || "field"}: ${d.msg}`)
            .join("; ");
    }
    if (!err.response) return "Can't reach the server. Is the backend running?";
    if (err.response.status === 403) return "Your role is not allowed to do this.";
    if (err.response.status >= 500) return "The server hit a problem. Please try again, or tell the admin.";
    return err.message;
}

// (select columns may also set `relatedList` - see the comment where relatedData is defined.)
// (any column may set `addOnly: true`: it is on the Add form only, hidden when editing and not sent on update -
//  used for the machine's starting project; later moves go through Transfers.)
// (select columns may also set `optionFilter: (item) => boolean` to offer only some options.)
// (select columns may also set `excludeSameAs: "<other column>"` to hide that column's
//  current value from their list — used for To Project vs From Project on Transfers.)
/**
 * Generic CRUD page. Pass a `config` describing one table and this
 * component handles fetching, creating, editing, and deleting rows for it.
 *
 * config shape:
 * {
 *   title: "Incidents",
 *   endpoint: "/incidents/",
 *   idField: "Incident_ID",
 *   columns: [
 *     { name: "Incident_ID", label: "Incident ID", editable: false },
 *
 *     // plain text/number/date input (unchanged from before):
 *     { name: "Incident_Date", label: "Incident Date", type: "date", required: true },
 *
 *     // dropdown sourced live from another table's endpoint, e.g. a foreign key
 *     {
 *       name: "Equipment_ID",
 *       label: "Equipment ID",
 *       type: "select",
 *       required: true,
 *       optionsEndpoint: "/equipment/",              // fetched once on mount
 *       optionValue: (item) => item.Equipment_ID,     // what gets saved
 *       optionLabel: (item) => `${item.Equipment_ID} - ${item.Equipment_Name}`, // what the user sees
 *       profileFields: [                              // OPTIONAL: read-only strip shown once a value is picked
 *         { name: "Equipment_Type", label: "Type" },
 *         { name: "Current_Status", label: "Status" },
 *       ],
 *     },
 *
 *     // NEW: a field whose value is auto-computed from another select's chosen option,
 *     // and locked so the user can't pick a mismatched value by hand.
 *     {
 *       name: "Project_ID",
 *       label: "Project ID",
 *       type: "derived",
 *       derivedFrom: "Equipment_ID",            // which select column drives this one
 *       derivedSourceField: "Current_Project_ID", // field on the chosen option to copy in
 *       required: true,
 *     },
 *   ],
 * }
 */
function EntityPage({ config }) {
    const { title, endpoint, idField } = config;
    const columns = applyOverrides(endpoint, config.columns);

    // Latest-entries mode: ask the server for just the newest rows (fast) instead of loading the whole table.
    // Set `recordsKey: null` in a page's config to keep the old "load everything + search" behaviour.
    // If the server has no records route for this page it quietly falls back to the old behaviour.
    const recordsKey = config.recordsKey === null ? null : config.recordsKey || endpoint.replace(/\//g, "");
    const [useRecords, setUseRecords] = useState(Boolean(recordsKey));
    const [total, setTotal] = useState(0);

    const [items, setItems] = useState([]);
    const [loading, setLoading] = useState(true);
    const [query, setQuery] = useState(""); // search box above the list
    const [error, setError] = useState(null);

    const editableColumns = columns.filter((col) => col.editable !== false);
    const selectColumns = editableColumns.filter((col) => col.type === "select");
    const autoIdColumn = editableColumns.find((col) => col.type === "autoid");
    const comboColumns = editableColumns.filter((col) => col.type === "combo");
    const [comboOptions, setComboOptions] = useState({}); // { Equipment_Type: ["Loader", ...] }
    // select columns with `relatedList` show a read-only line under the dropdown, e.g. the machines that are
    // currently at the chosen project: relatedList: { endpoint, matchField, title, label: (item) => text }
    const [relatedData, setRelatedData] = useState({});
    // "choice" columns that allow an "Other (specify)" option get a companion
    // text field, e.g. Incident_Type -> Incident_Type_Other, stored as its own
    // DB column so the canonical dropdown value stays clean for analytics.
    const otherColumns = editableColumns.filter((col) => col.type === "choice" && col.allowOther);
    const otherFieldName = (col) => `${col.name}_Other`;

    const emptyForm = Object.fromEntries([
        ...editableColumns.map((col) => [col.name, col.defaultValue ?? ""]),
        ...otherColumns.map((col) => [otherFieldName(col), ""]),
    ]);
    const [formValues, setFormValues] = useState(emptyForm);
    const [submitError, setSubmitError] = useState(null);

    // null = creating a new row. Otherwise holds the idField value of the row being edited.
    const [editingId, setEditingId] = useState(null);

    // Options for every "select" column, fetched once: { Equipment_ID: [...rows from /equipment/], ... }
    const [selectOptions, setSelectOptions] = useState({});

    // Lets us scroll the form into view when Edit is clicked on a row far down a long table.
    const formRef = useRef(null);

    const fetchItems = () => {
        if (useRecords) {
            apiClient
                .get(`/records/${recordsKey}`, { params: { page_size: LATEST_COUNT } })
                .then((response) => {
                    setItems(response.data.rows);
                    setTotal(response.data.total);
                    setLoading(false);
                })
                .catch((err) => {
                    if (err.response?.status === 404) setUseRecords(false); // no records route -> old behaviour
                    else {
                        setError(formatApiError(err));
                        setLoading(false);
                    }
                });
            return;
        }
        apiClient
            .get(endpoint)
            .then((response) => {
                setItems(response.data);
                setTotal(response.data.length);
                setLoading(false);
            })
            .catch((err) => {
                setError(formatApiError(err));
                setLoading(false);
            });
    };

    useEffect(() => {
        fetchItems();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [endpoint, useRecords]);

    // Suggestions for "combo" fields (one request per distinct endpoint).
    useEffect(() => {
        [...new Set(comboColumns.map((c) => c.optionsEndpoint))].forEach((url) => {
            apiClient
                .get(url)
                .then((res) => {
                    const next = {};
                    comboColumns.filter((c) => c.optionsEndpoint === url).forEach((c) => {
                        next[c.name] = res.data[c.optionsKey] || [];
                        if (c.pricedKey) next[`${c.name}__priced`] = res.data[c.pricedKey] || [];
                    });
                    setComboOptions((prev) => ({ ...prev, ...next }));
                })
                .catch(() => {});
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [endpoint]);

    // "autoid" field: show the next free ID while creating a new record.
    const autoIdValue = autoIdColumn ? formValues[autoIdColumn.name] : null;
    useEffect(() => {
        if (!autoIdColumn || editingId !== null || autoIdValue !== "") return;
        apiClient
            .get(autoIdColumn.nextIdEndpoint)
            .then((res) => setFormValues((prev) => ({ ...prev, [autoIdColumn.name]: res.data.next_id })))
            .catch(() => {});
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [autoIdColumn?.name, editingId, autoIdValue]);

    // Fetch each select column's option list once, in parallel.
    useEffect(() => {
        selectColumns.forEach((col) => {
            apiClient
                .get(col.optionsEndpoint)
                .then((response) => {
                    setSelectOptions((prev) => ({ ...prev, [col.name]: response.data }));
                })
                .catch(() => {
                    setSelectOptions((prev) => ({ ...prev, [col.name]: [] }));
                });
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [endpoint]);

    useEffect(() => {
        selectColumns.filter((col) => col.relatedList).forEach((col) => {
            apiClient
                .get(col.relatedList.endpoint)
                .then((res) => setRelatedData((prev) => ({ ...prev, [col.name]: res.data })))
                .catch(() => {});
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [endpoint]);

    // Columns with `displayLookup` show a name next to their ID (Project_ID -> "PRJ-010 - Highway Section B").
    const [lookups, setLookups] = useState({});
    useEffect(() => {
        [...new Set(columns.filter((c) => c.displayLookup).map((c) => c.displayLookup.endpoint))].forEach((url) => {
            apiClient
                .get(url)
                .then((res) => setLookups((prev) => ({ ...prev, [url]: res.data })))
                .catch(() => {});
        });
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [endpoint]);
    const lookupText = (col, value) => {
        if (value === "" || value === null || value === undefined) return "";
        const lk = col.displayLookup;
        if (!lk) return String(value);
        const match = (lookups[lk.endpoint] || []).find((i) => String(i[lk.key]) === String(value));
        return match ? `${value} - ${lk.text(match)}` : String(value);
    };

    const handleFieldChange = (name, value) => {
        // columns marked `uppercase: true` (IDs) are always typed in capitals
        if (columns.find((c) => c.name === name)?.uppercase && typeof value === "string") value = value.toUpperCase();
        setFormValues((prev) => ({ ...prev, [name]: value }));
    };

    // Used specifically for "select" columns: also updates any "derived" fields that
    // depend on this one (e.g. picking an Equipment_ID auto-fills Project_ID from it).
    const handleSelectChange = (col, value) => {
        const options = selectOptions[col.name] || [];
        const chosenItem = options.find((opt) => String(col.optionValue(opt)) === String(value));

        setFormValues((prev) => {
            const next = { ...prev, [col.name]: value };
            editableColumns.forEach((otherCol) => {
                if (otherCol.derivedFrom === col.name) {
                    next[otherCol.name] = chosenItem
                        ? chosenItem[otherCol.derivedSourceField] ?? ""
                        : "";
                }
            });
            // If a dropdown must differ from another field (e.g. To Project vs the
            // auto-filled From Project) and the two now match, clear it. This runs
            // after derived fields update, so changing Equipment can't leave a
            // same-project transfer sitting in the form.
            editableColumns.forEach((dep) => {
                if (dep.excludeSameAs && next[dep.excludeSameAs] !== "" &&
                    String(next[dep.name]) === String(next[dep.excludeSameAs])) {
                    next[dep.name] = "";
                }
            });
            return next;
        });
    };

    const handleEditClick = (item) => {
        const nextFormValues = {};
        editableColumns.forEach((col) => {
            nextFormValues[col.name] = item[col.name] ?? "";
        });
        otherColumns.forEach((col) => {
            nextFormValues[otherFieldName(col)] = item[otherFieldName(col)] ?? "";
        });
        setFormValues(nextFormValues);
        setEditingId(item[idField]);
        setSubmitError(null);

        // Bring the form into view so editing a row far down a long table
        // doesn't leave the user wondering why nothing seems to have happened.
        formRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
    };

    const handleCancelEdit = () => {
        setFormValues(emptyForm);
        setEditingId(null);
        setSubmitError(null);
    };

    const handleSubmit = (e) => {
        e.preventDefault();
        setSubmitError(null);

        // A locked "derived" field can't be filled in by hand, and the browser skips
        // validation on disabled inputs — so check here and explain what went wrong.
        const emptyDerived = editableColumns.find(
            (col) => col.type === "derived" && col.required && formValues[col.name] === ""
        );
        if (emptyDerived) {
            setSubmitError(
                `${emptyDerived.label} could not be auto-filled from the selected ${emptyDerived.derivedFrom} — ` +
                `it has no current project assigned. Assign it a project first.`
            );
            return;
        }

        const payload = {};
        editableColumns.forEach((col) => {
            if (col.addOnly && editingId) return; // add-only columns are not part of an update
            const value = formValues[col.name];
            payload[col.name] = value === "" ? null : value;
        });
        otherColumns.forEach((col) => {
            const value = formValues[otherFieldName(col)];
            payload[otherFieldName(col)] = value === "" ? null : value;
        });

        // Creating with an auto ID: ask for the next free number again right now (someone else may have
        // saved a record since this form was opened), then save.
        const freshId =
            autoIdColumn && !editingId
                ? apiClient.get(autoIdColumn.nextIdEndpoint).then((res) => res.data.next_id)
                : Promise.resolve(null);

        // Editing an existing row -> PUT to /endpoint/{id}. Creating -> POST to /endpoint/.
        freshId
            .then((newId) => {
                if (newId) payload[autoIdColumn.name] = newId;
                return editingId
                    ? apiClient.put(`${endpoint}${editingId}`, payload)
                    : apiClient.post(endpoint, payload);
            })
            .then(() => {
                setFormValues(emptyForm);
                setEditingId(null);
                fetchItems();
            })
            .catch((err) => {
                setSubmitError(formatApiError(err));
            });
    };

    const handleDelete = (id) => {
        if (!window.confirm(`Delete this record (${idField} = ${id})?`)) return;

        apiClient
            .delete(`${endpoint}${id}`)
            .then(() => {
                fetchItems();
            })
            .catch((err) => {
                alert(formatApiError(err));
            });
    };

    // When the page has its own Unit column, the amount itself is shown as a plain number.
    const hasUnitColumn = columns.some((c) => c.unitOnly);
    // Number columns whose unit depends on the machine picked in another column (Fuel Consumed: litres / kWh).
    const unitOf = (col, source) => {
        const options = selectOptions[col.unitFrom] || [];
        const machine = options.find((o) => String(o[col.unitFrom]) === String(source));
        return machine ? fuelUnit(machine[col.unitSourceField]) : null;
    };
    const labelOf = (col) => {
        if (!col.unitFrom) return col.label;
        const unit = unitOf(col, formValues[col.unitFrom]);
        return `${col.label} (${unit || "litres / kWh"})`;
    };

    if (loading) return <p>Loading {title}...</p>;
    if (error) return <p>Error: {error}</p>;

    // Search box: keeps rows where ANY value contains the typed text (case-insensitive).
    const needle = query.trim().toLowerCase();
    // It also looks at the friendly text shown in dropdown columns (e.g. "PRJ-001 - Apex Mining Sector B"),
    // so searching "apex" finds that project's rows, not only the raw ID.
    const shownText = (item) =>
        selectColumns
            .map((col) => {
                const match = (selectOptions[col.name] || []).find(
                    (opt) => String(col.optionValue(opt)) === String(item[col.name])
                );
                return match ? (col.tableLabel || col.optionLabel)(match) : "";
            })
            .join(" ");
    const visibleItems = needle
        ? items.filter(
              (item) =>
                  Object.values(item).some((v) => String(v ?? "").toLowerCase().includes(needle)) ||
                  shownText(item).toLowerCase().includes(needle)
          )
        : items;

    return (
        <div>
            <h2>{title}</h2>

            <form onSubmit={handleSubmit} className="card-panel entity-form" ref={formRef}>
                <div className="card-head">
                    <div>
                        <h3 className="card-title">{editingId ? "Edit entry" : "New entry"}</h3>
                        <div className="card-sub">
                            {editingId ? `Change the fields below, then press Update. (${title})` : `Fill in the fields below, then press Add. (${title})`}
                        </div>
                    </div>
                </div>
                <div className="form-body">
                <div className="form-grid">
                {editableColumns.filter((col) => !(col.addOnly && editingId)).map((col) => (
                    <div className="field" key={col.name}>
                    <label className="field-label">{labelOf(col)}{col.required ? " *" : ""}</label>
                    {(() => {
                    if (col.type === "select") {
                        const options = selectOptions[col.name] || [];
                        // Once something is picked, find its full record so we can show the profile strip.
                        const selectedValue = formValues[col.name];
                        const selectedItem = options.find(
                            (opt) => String(col.optionValue(opt)) === String(selectedValue)
                        );
                        // col.excludeSameAs: hide whatever is picked in that other field
                        // (e.g. To Project can't offer the From Project).
                        let visibleOptions = col.excludeSameAs
                            ? options.filter(
                                  (opt) =>
                                      String(col.optionValue(opt)) !== String(formValues[col.excludeSameAs] ?? "")
                              )
                            : options;
                        // col.optionFilter: only offer options that pass (e.g. only Active / On Hold projects).
                        // The value already chosen stays in the list, so editing an old row still shows it.
                        if (col.optionFilter) {
                            visibleOptions = visibleOptions.filter(
                                (opt) =>
                                    col.optionFilter(opt) ||
                                    String(col.optionValue(opt)) === String(formValues[col.name] ?? "")
                            );
                        }

                        return (
                            <span key={col.name} style={{ marginRight: "8px", display: "inline-block" }}>
                                <select
                                    value={selectedValue}
                                    onChange={(e) => handleSelectChange(col, e.target.value)}
                                    required={col.required}
                                >
                                    <option value="">
                                        {options.length === 0
                                            ? `No ${col.label} found — add one first`
                                            : `Select ${col.label}`}
                                    </option>
                                    {visibleOptions.map((opt) => (
                                        <option key={col.optionValue(opt)} value={col.optionValue(opt)}>
                                            {col.optionLabel(opt)}
                                        </option>
                                    ))}
                                </select>

                                {col.profileFields && selectedItem && (
                                    <span
                                        style={{
                                            marginLeft: "8px",
                                            padding: "2px 8px",
                                            border: "1px solid #888",
                                            borderRadius: "4px",
                                            fontSize: "0.9em",
                                        }}
                                    >
                                        {col.profileFields
                                            .map((pf) => `${pf.label}: ${selectedItem[pf.name] ?? "—"}`)
                                            .join("  |  ")}
                                    </span>
                                )}
                                {col.relatedList && selectedValue && (() => {
                                    const rl = col.relatedList;
                                    const list = (relatedData[col.name] || []).filter(
                                        (i) => String(i[rl.matchField]) === String(selectedValue)
                                    );
                                    const names = list.slice(0, 8).map(rl.label).join(", ");
                                    return (
                                        <div className="field-hint" style={{ marginTop: "6px" }}>
                                            {rl.title}: {list.length === 0 ? "none right now" : `${list.length} - ${names}${list.length > 8 ? ` and ${list.length - 8} more` : ""}`}
                                        </div>
                                    );
                                })()}
                            </span>
                        );
                    }

                    if (col.type === "choice") {
                        // A fixed dropdown list defined right in the config (col.options),
                        // not fetched from another table — for categorical fields like
                        // Maintenance_Type where the valid values are a known short list.
                        //
                        // col.allowOther adds an "Other (specify)" choice. Picking it reveals
                        // a required text box whose value is saved to a SEPARATE companion
                        // column (<name>_Other), NOT written back into this column — the
                        // canonical dropdown value stays "Other" so grouping/analytics on
                        // this field stays clean, while the actual free text lives alongside
                        // it for anyone reading the individual record.
                        const choiceOptions = col.allowOther ? [...col.options, "Other"] : col.options;
                        const otherKey = otherFieldName(col);
                        const isOtherSelected = col.allowOther && formValues[col.name] === "Other";

                        return (
                            <span key={col.name} style={{ marginRight: "8px", display: "inline-block" }}>
                                <select
                                    value={formValues[col.name]}
                                    onChange={(e) => handleFieldChange(col.name, e.target.value)}
                                    required={col.required}
                                    style={{ marginRight: "8px" }}
                                >
                                    <option value="">
                                        {col.required ? `Select ${col.label}` : `${col.label} (optional)`}
                                    </option>
                                    {choiceOptions.map((opt) => (
                                        <option key={opt} value={opt}>
                                            {opt}
                                        </option>
                                    ))}
                                </select>

                                {isOtherSelected && (
                                    <input
                                        type="text"
                                        value={formValues[otherKey]}
                                        placeholder={col.otherPlaceholder || `Specify ${col.label}`}
                                        onChange={(e) => handleFieldChange(otherKey, e.target.value)}
                                        required
                                        style={{ marginRight: "8px" }}
                                    />
                                )}
                            </span>
                        );
                    }

                    if (col.type === "autoid") {
                        return (
                            <input
                                key={col.name}
                                type="text"
                                value={formValues[col.name]}
                                placeholder="Assigned automatically"
                                readOnly
                                disabled
                                title="Generated automatically - the next free number"
                                style={{ backgroundColor: "#eee", color: "#555" }}
                            />
                        );
                    }

                    if (col.type === "combo") {
                        const listId = `list-${col.name}`;
                        const suggestions = comboOptions[col.name] || [];
                        // Typing "loader" when "Loader" already exists snaps to the existing spelling.
                        const snapToExisting = (e) => {
                            const typed = e.target.value.trim();
                            const match = suggestions.find((o) => o.toLowerCase() === typed.toLowerCase());
                            handleFieldChange(col.name, match || typed);
                        };
                        return (
                            <span key={col.name}>
                                <input
                                    type="text"
                                    list={listId}
                                    value={formValues[col.name]}
                                    placeholder={col.required ? `Select or type ${col.label}` : `${col.label} (optional)`}
                                    onChange={(e) => handleFieldChange(col.name, e.target.value)}
                                    onBlur={snapToExisting}
                                    required={col.required}
                                />
                                <datalist id={listId}>
                                    {suggestions.map((o) => (
                                        <option key={o} value={o} />
                                    ))}
                                </datalist>
                                {(() => {
                                    // e.g. a Fuel Type that has no price yet: warn now instead of failing later on the Fuel form
                                    const priced = comboOptions[`${col.name}__priced`];
                                    const typed = String(formValues[col.name] || "").trim();
                                    const known = priced && priced.some((o) => o.toLowerCase() === typed.toLowerCase());
                                    return priced && typed && !known ? (
                                        <div className="field-hint">
                                            No fuel price set for '{typed}' yet - ask a Fleet Manager to add it in Fuel Rates.
                                        </div>
                                    ) : null;
                                })()}
                            </span>
                        );
                    }

                    if (col.type === "textarea") {
                        return (
                            <textarea
                                key={col.name}
                                placeholder={col.required ? col.label : `${col.label} (optional)`}
                                value={formValues[col.name]}
                                onChange={(e) => handleFieldChange(col.name, e.target.value)}
                                required={col.required}
                                rows={3}
                                style={{ display: "block", width: "100%", maxWidth: "500px", marginBottom: "8px" }}
                            />
                        );
                    }

                    if (col.type === "derived") {
                        return (
                            <input
                                key={col.name}
                                type="text"
                                value={col.displayLookup ? lookupText(col, formValues[col.name]) : formValues[col.name]}
                                placeholder={`${col.label} (auto-filled from ${col.derivedFrom})`}
                                readOnly
                                disabled
                                style={{ marginRight: "8px", backgroundColor: "#eee", color: "#555" }}
                            />
                        );
                    }

                    return (
                        <input
                            key={col.name}
                            type={col.type || "text"}
                            placeholder={col.required ? col.label : `${col.label} (optional)`}
                            value={formValues[col.name]}
                            onChange={(e) => handleFieldChange(col.name, e.target.value)}
                            required={col.required}
                            min={col.min}
                            max={col.max}
                            step={col.step}
                            // The primary key can't actually be changed via an update (the backend
                            // identifies the row by the URL, not this field), so lock it while editing
                            // to avoid confusing the user into thinking it's renaming the record.
                            disabled={editingId !== null && col.name === idField}
                            style={{ marginRight: "8px" }}
                        />
                    );
                    })()}
                    </div>
                ))}
                </div>
                <div className="form-actions">
                    <button type="submit">{editingId ? "Update" : "Add"}</button>
                    {editingId && (
                        <button type="button" className="btn-outline" onClick={handleCancelEdit}>
                            Cancel
                        </button>
                    )}
                </div>
                {submitError && <p className="form-error">{submitError}</p>}
                </div>
            </form>

            <div className="card-panel">
                <div className="card-head">
                    <div>
                        <h3 className="card-title">{useRecords ? "Latest entries" : "Saved records"}</h3>
                        <div className="card-sub">
                            {useRecords
                                ? "Your newest entries - use Edit or Delete here to fix a mistake. To search, filter or download, open all records."
                                : "Search by any value — for example an equipment ID."}
                        </div>
                    </div>
                    {useRecords ? (
                        <div className="list-tools">
                            <span className="list-count">
                                Latest {items.length} of {total}
                            </span>
                            <Link className="btn-link" to={`/records/${recordsKey}`}>
                                View all records &rarr;
                            </Link>
                        </div>
                    ) : (
                        <div className="list-tools">
                            <input
                                className="list-search"
                                type="search"
                                placeholder={`Search ${title.toLowerCase()}...`}
                                value={query}
                                onChange={(e) => setQuery(e.target.value)}
                            />
                            <span className="list-count">
                                Showing {visibleItems.length} of {items.length}
                            </span>
                        </div>
                    )}
                </div>
                <div className="table-scroll">

            <table>
                <thead>
                    <tr>
                        {columns.map((col) => (
                            <th key={col.name}>{col.unitFrom && !col.unitOnly && !hasUnitColumn ? `${col.label} (litres / kWh)` : col.label}</th>
                        ))}
                        <th>Actions</th>
                    </tr>
                </thead>
                <tbody>
                    {visibleItems.map((item) => (
                        <tr key={item[idField]}>
                            {columns.map((col) => {
                                // For a "select" column (e.g. Equipment_ID), show the friendly
                                // label (ID + Name) in the table too, not just the raw ID —
                                // matches whatever the dropdown itself displays while editing.
                                let displayValue = item[col.name];
                                if (col.type === "select") {
                                    const options = selectOptions[col.name] || [];
                                    const matched = options.find(
                                        (opt) => String(col.optionValue(opt)) === String(item[col.name])
                                    );
                                    if (matched) displayValue = (col.tableLabel || col.optionLabel)(matched);
                                }
                                if (col.type === "choice" && col.allowOther && displayValue === "Other") {
                                    const otherText = item[otherFieldName(col)];
                                    displayValue = otherText ? `Other: ${otherText}` : "Other";
                                }
                                if (col.unitOnly) {
                                    displayValue = unitOf(col, item[col.unitFrom]) || ""; // the separate Unit column
                                } else if (col.unitFrom && !hasUnitColumn && displayValue !== null && displayValue !== undefined) {
                                    const unit = unitOf(col, item[col.unitFrom]);
                                    if (unit) displayValue = `${displayValue} ${unit}`;
                                }
                                if (col.displayLookup) displayValue = lookupText(col, displayValue);
                                if (col.type === "time" && displayValue) {
                                    displayValue = String(displayValue).slice(0, 5); // show HH:MM, not seconds
                                }
                                return <td key={col.name}>{String(displayValue ?? "")}</td>;
                            })}
                            <td>
                                <button onClick={() => handleEditClick(item)} style={{ marginRight: "8px" }}>
                                    Edit
                                </button>
                                <button onClick={() => handleDelete(item[idField])}>
                                    Delete
                                </button>
                            </td>
                        </tr>
                    ))}
                </tbody>
            </table>
            {visibleItems.length === 0 && <div className="empty-row">No records match.</div>}
                </div>
            </div>
        </div>
    );
}

export default EntityPage;

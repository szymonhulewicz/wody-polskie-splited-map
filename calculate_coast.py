def calculate_coast_aal(df, coord_list, df_wp):
    typ = "coast"
    scenariusze = ["historical", "rcp8p5"]
    osiadanie = ["wtsub"]
    lata = ["hist", "2080"]
    okresy = ["0010", "0100", "0500"]
    prawdopodobienstwa = ["0"]

    df_coast = None

    for scen in scenariusze:
        for subs in osiadanie:
            for rok in lata:
                for rp in okresy:
                    for prob in prawdopodobienstwa:

                        plik_zrodlo = (
                            f"/home/ailab-user/aqueduct/aqueduct_flood_risk_map/"
                            f"{typ}/inun{typ}_{scen}_{subs}_{rok}_rp{rp}_{prob}.tif"
                        )

                        if os.path.exists(plik_zrodlo):
                            print(plik_zrodlo)

                            df_tmp = df.copy()
                            df_tmp["scen"] = scen
                            df_tmp["osiadanie"] = subs
                            df_tmp["rok"] = rok
                            df_tmp["okres_zwrotu"] = rp
                            df_tmp["prawdop"] = prob

                            with rasterio.open(plik_zrodlo) as plik:
                                df_tmp["glebokosc_m"] = [
                                    x[0] for x in plik.sample(coord_list)
                                ]

                            if df_coast is not None:
                                df_coast = pd.concat(
                                    [df_coast, df_tmp],
                                    ignore_index=True
                                )
                            else:
                                df_coast = df_tmp.copy()
                        else:
                            print(f"{plik_zrodlo} nie istnieje.")

    if df_coast is None:
        return 0.0

    df_coast = df_coast.rename(columns={
        "scen": "SCEN",
        "rok": "ROK",
        "okres_zwrotu": "OKRES_ZWROTU",
        "glebokosc_m": "GLEBOKOSC_M"
    })

    df_hist_coast = df_coast[df_coast["SCEN"] == "historical"].copy()
    df_models_coast = df_coast[df_coast["SCEN"] != "historical"].copy()

    df_hist_coast = df_hist_coast.rename(columns={
        "GLEBOKOSC_M": "GLEBOKOSC_HIST"
    })

    df_rez_coast = df_models_coast.merge(
        df_hist_coast[[
            "EXPOSURE_ID",
            "OKRES_ZWROTU",
            "GLEBOKOSC_HIST"
        ]],
        on=["EXPOSURE_ID", "OKRES_ZWROTU"],
        how="left"
    )

    df_rez_coast["OKRES_ZWROTU"] = pd.to_numeric(
        df_rez_coast["OKRES_ZWROTU"],
        errors="coerce"
    )

    df_wp_coast = df_wp[df_wp["TYP"] == "Morze"].copy()

    if df_wp_coast.empty:
        return 0.0

    df_rez_coast = df_rez_coast.merge(
        df_wp_coast[[
            "EXPOSURE_ID",
            "OKRES_ZWROTU",
            "GLEBOKOSC",
            "DEPTH_M"
        ]],
        on=["EXPOSURE_ID", "OKRES_ZWROTU"],
        how="left"
    )

    df_rez_coast["DEPTH_DELTA_ABSOLUTE"] = (
        df_rez_coast["GLEBOKOSC_M"] - df_rez_coast["GLEBOKOSC_HIST"]
    )

    df_rez_coast["DEPTH_DELTA_RELATIVE"] = (
        df_rez_coast["GLEBOKOSC_M"] / df_rez_coast["GLEBOKOSC_HIST"]
    )

    df_rez_coast.loc[
        df_rez_coast["GLEBOKOSC_M"] == df_rez_coast["GLEBOKOSC_HIST"],
        "DEPTH_DELTA_RELATIVE"
    ] = 1

    bins = [float("-inf"), 0, 0.5, 2, 4, float("inf")]
    labels = [0, 1, 2, 3, 4]

    df_rez_coast["DEPTH_BUCKET_HIST"] = pd.cut(
        df_rez_coast["GLEBOKOSC_HIST"],
        bins=bins,
        labels=labels,
        right=True
    )

    df_rez_coast["DEPTH_BUCKET_MOD"] = pd.cut(
        df_rez_coast["GLEBOKOSC_M"],
        bins=bins,
        labels=labels,
        right=True
    )

    df_rez_coast["DEPTH_BUCKET_HIST"] = pd.to_numeric(
        df_rez_coast["DEPTH_BUCKET_HIST"],
        errors="coerce"
    )

    df_rez_coast["DEPTH_BUCKET_MOD"] = pd.to_numeric(
        df_rez_coast["DEPTH_BUCKET_MOD"],
        errors="coerce"
    )

    df_rez_coast["DEPTH_BUCKET_DELTA"] = (
        df_rez_coast["DEPTH_BUCKET_MOD"] - df_rez_coast["DEPTH_BUCKET_HIST"]
    )

    df_rez_coast["GLEBOKOSC"] = df_rez_coast["GLEBOKOSC"].fillna(0)
    df_rez_coast["DEPTH_M"] = df_rez_coast["DEPTH_M"].fillna(0)

    df_rez_coast["DEPTH_M_X_DELTA_RELATIVE"] = (
        df_rez_coast["DEPTH_M"] * df_rez_coast["DEPTH_DELTA_RELATIVE"]
    )

    df_rez_coast["WP_SCEN_BUCKET"] = np.where(
        df_rez_coast["DEPTH_DELTA_RELATIVE"] == np.inf,
        np.maximum(
            df_rez_coast["GLEBOKOSC"],
            df_rez_coast["GLEBOKOSC"] + df_rez_coast["DEPTH_BUCKET_DELTA"]
        ),
        pd.cut(
            df_rez_coast["DEPTH_M_X_DELTA_RELATIVE"],
            bins=bins,
            labels=labels,
            right=True
        )
    )

    df_rez_coast.loc[
        df_rez_coast["DEPTH_DELTA_RELATIVE"] == 0,
        "WP_SCEN_BUCKET"
    ] = np.maximum(
        df_rez_coast["GLEBOKOSC"],
        df_rez_coast["GLEBOKOSC"] + df_rez_coast["DEPTH_BUCKET_DELTA"]
    )

    df_rez_coast.loc[
        (df_rez_coast["DEPTH_DELTA_RELATIVE"] != np.inf) &
        (df_rez_coast["GLEBOKOSC"] == 0),
        "WP_SCEN_BUCKET"
    ] = np.maximum(
        df_rez_coast["GLEBOKOSC"],
        df_rez_coast["GLEBOKOSC"] + df_rez_coast["DEPTH_BUCKET_DELTA"]
    )

    df_rez_coast["WP_SCEN_BUCKET_RELATIVE"] = pd.to_numeric(
        df_rez_coast["WP_SCEN_BUCKET"],
        errors="coerce"
    )

    df_rez_coast["DEPTH_WP_M_SCEN_ABS"] = np.maximum(
        df_rez_coast["DEPTH_M"] + df_rez_coast["DEPTH_DELTA_ABSOLUTE"],
        0
    )

    df_rez_coast["DEPTH_BUCKET_WP_SCEN"] = pd.cut(
        df_rez_coast["DEPTH_WP_M_SCEN_ABS"],
        bins=bins,
        labels=labels,
        right=True
    )

    df_rez_coast["DEPTH_BUCKET_WP_SCEN"] = pd.to_numeric(
        df_rez_coast["DEPTH_BUCKET_WP_SCEN"],
        errors="coerce"
    )

    df_rez_coast["WP_SCEN_FULL_BUCKET_COR"] = np.where(
        (df_rez_coast["DEPTH_BUCKET_WP_SCEN"] == df_rez_coast["GLEBOKOSC"]) &
        (df_rez_coast["DEPTH_BUCKET_DELTA"] != 0),
        np.maximum(
            0,
            df_rez_coast["DEPTH_BUCKET_WP_SCEN"] + df_rez_coast["DEPTH_BUCKET_DELTA"]
        ),
        df_rez_coast["DEPTH_BUCKET_WP_SCEN"]
    )

    df_rez_coast["WP_SCEN_FULL_BUCKET_COR_ABS"] = np.where(
        (df_rez_coast["GLEBOKOSC"] == 0) &
        (df_rez_coast["DEPTH_BUCKET_DELTA"] == 0),
        0,
        df_rez_coast["WP_SCEN_FULL_BUCKET_COR"]
    )

    df_rez_coast["PROB"] = 1 / df_rez_coast["OKRES_ZWROTU"]

    df_rez_coast["DAMAGE_VALUE_ABS"] = (
        df_rez_coast["WP_SCEN_FULL_BUCKET_COR_ABS"]
        .replace(damage_curve)
    )

    df_rez_coast["DAMAGE_VALUE_RELATIVE"] = (
        df_rez_coast["WP_SCEN_BUCKET_RELATIVE"]
        .replace(damage_curve)
    )

    df_rez_coast["DAMAGE_VALUE"] = df_rez_coast["DAMAGE_VALUE_RELATIVE"]

    df_sorted_coast = df_rez_coast.sort_values(
        by=["EXPOSURE_ID", "SCEN", "ROK", "PROB"],
        ascending=[True, True, True, False]
    )

    aals_per_contract_coast = (
        df_sorted_coast
        .groupby(["EXPOSURE_ID", "SCEN", "ROK"], as_index=False)
        .apply(calculate_aal, include_groups=False)
        .reset_index(drop=True)
    )

    aals_per_contract_coast.columns = [
        "EXPOSURE_ID",
        "SCEN",
        "ROK",
        "AAL"
    ]

    final_result_coast = aals_per_contract_coast[
        (aals_per_contract_coast["SCEN"].astype(str).str.strip() == "rcp8p5") &
        (aals_per_contract_coast["ROK"].astype(str).str.strip() == "2080")
    ].copy()

    if final_result_coast.empty:
        return 0.0

    return float(final_result_coast["AAL"].iloc[0])
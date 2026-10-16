from vdamkc import data, reference

TRAP_HEADER = "trap_id,site_name,latitude,longitude,date,collection_method,species,sex,count\n"
RES_HEADER = "site_name,date,insecticide,exposure_time_min,sample_size,mortality_percent\n"


def _levels(result):
    return [i.level for i in result.issues]


class TestTrapLoading:
    def test_sample_file_loads_cleanly(self):
        result = data.load_trap_data(data.DEFAULT_TRAP_PATH)
        assert result.ok and not result.df.empty
        assert not [i for i in result.issues if i.level != "info"]

    def test_missing_column_is_an_error(self):
        result = data.load_trap_data(b"site_name,date\nA,2026-01-01\n")
        assert not result.ok
        assert "count" in result.issues[0].message

    def test_headers_are_normalised_and_bom_tolerated(self):
        raw = "﻿Trap ID,Site Name,Latitude,Longitude,Date,Collection Method,Species,Sex,Count\n" \
              "T1,A,11.8,13.1,2026-05-01,CDC,Anopheles gambiae,female,3\n"
        result = data.load_trap_data(raw.encode("utf-8"))
        assert result.ok and len(result.df) == 1
        assert result.df.loc[0, "sex"] == "Female"

    def test_bad_rows_are_dropped_and_reported(self):
        raw = TRAP_HEADER + (
            "T1,A,11.8,13.1,2026-05-01,CDC,An,Female,3\n"
            "T1,A,11.8,13.1,not-a-date,CDC,An,Female,3\n"
            "T1,A,95,13.1,2026-05-02,CDC,An,Female,3\n"
            "T1,A,11.8,13.1,2026-05-03,CDC,An,Female,-1\n"
        )
        result = data.load_trap_data(raw.encode())
        assert len(result.df) == 1
        messages = " ".join(i.message for i in result.issues)
        assert "CSV rows: 3" in messages and "CSV rows: 4" in messages and "CSV rows: 5" in messages

    def test_exact_duplicates_are_not_double_counted(self):
        row = "T1,A,11.8,13.1,2026-05-01,CDC,An,Female,3\n"
        result = data.load_trap_data((TRAP_HEADER + row + row).encode())
        assert result.df["count"].sum() == 3
        assert "warning" in _levels(result)

    def test_cp1252_files_are_readable(self):
        raw = TRAP_HEADER + "T1,Gwangé,11.8,13.1,2026-05-01,CDC,An,Female,3\n"
        result = data.load_trap_data(raw.encode("cp1252"))
        assert result.df.loc[0, "site_name"] == "Gwangé"

    def test_empty_file(self):
        assert not data.load_trap_data(b"").ok


class TestResistanceLoading:
    def test_out_of_range_mortality_is_dropped(self):
        raw = RES_HEADER + "A,2026-05-01,Delta,60,100,92\nA,2026-05-02,Delta,60,100,120\n"
        result = data.load_resistance_data(raw.encode())
        assert len(result.df) == 1

    def test_missing_control_column_is_noted_not_fatal(self):
        result = data.load_resistance_data((RES_HEADER + "A,2026-05-01,Delta,60,100,92\n").encode())
        assert result.ok
        assert any("Abbott" in i.message for i in result.issues)


def test_csv_export_neutralises_formulas():
    import pandas as pd
    out = data.safe_csv_bytes(pd.DataFrame({"site": ["=HYPERLINK(1)", "Fori"]})).decode()
    assert "'=HYPERLINK" in out and "\nFori" in out


class TestAtlasMatching:
    def test_exact_and_abbreviated_names_match(self):
        assert reference.match_species("Anopheles gambiae")["id"] == "anopheles_gambiae"
        assert reference.match_species("An. funestus s.s.")["id"] == "anopheles_funestus"
        assert reference.match_species("anopheles  coluzzii")["id"] == "anopheles_coluzzii"

    def test_sensu_lato_is_recorded(self):
        ref = reference.species_reference(["An. gambiae s.l."])
        assert ref.loc[0, "recorded_as"] == "sensu lato"
        assert ref.loc[0, "complex_or_group"] == "An. gambiae complex"

    def test_typos_are_flagged(self):
        assert reference.unrecognised_species(["Anopheles gambiae", "Anopheles gambaie"]) == ["Anopheles gambaie"]

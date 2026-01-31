from app import _run_pipeline, load_cases

def main():
    cases = load_cases()
    results = {}
    for cid in cases:
        case = cases[cid]
        result = _run_pipeline(case, [])
        scenario = cases[cid]['meta']['scenario']
        guardrail_status = result['guardrail_report']['status']
        # Simple check: for gotcha case, expect FAIL if iron action present
        if scenario == 'anemia_of_inflammation':
            has_inflammation = "Inflammation-mediated iron sequestration" in result['case_card']['signals']
            has_iron_action = any("iron" in a['task'].lower() for a in result['reasoner_output']['patient_actions'])
            expected_fail = has_inflammation and has_iron_action
            pass_fail = (guardrail_status == 'FAIL') == expected_fail
        else:
            pass_fail = guardrail_status == 'PASS'
        results[cid] = pass_fail

    print("Eval results:")
    for cid, pf in results.items():
        print(f"{cid}: {'PASS' if pf else 'FAIL'}")
    total_pass = sum(results.values())
    print(f"Total: {total_pass}/{len(results)}")

if __name__ == "__main__":
    main()
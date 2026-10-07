import csv
import re
import ipaddress

CASES_FILE = "../data/cases.csv"


def check_duplicate_ip(text):
    """Detect duplicate IP addresses when assigned to multiple PCs."""
    pairs = re.findall(
        r'(PC-\d+)\s*(?:IP|IP address)[:\s]+(\d+\.\d+\.\d+\.\d+)',
        text,
        re.IGNORECASE
    )

    ips = [ip for _, ip in pairs]

    return len(ips) != len(set(ips)) if ips else False


def check_gateway_mismatch(text):
    """Check whether the configured gateway belongs to the PC subnet."""
    ip_match = re.search(
        r'PC-\d+:\s*IP\s+(\d+\.\d+\.\d+\.\d+)',
        text,
        re.IGNORECASE
    )

    mask_match = re.search(
        r'(?:Mask|mask)\s+(\d+\.\d+\.\d+\.\d+)',
        text
    )

    gateway_match = re.search(
        r'Gateway\s+(\d+\.\d+\.\d+\.\d+)',
        text,
        re.IGNORECASE
    )

    if not (ip_match and mask_match and gateway_match):
        return False

    try:
        network = ipaddress.ip_network(
            f"{ip_match.group(1)}/{mask_match.group(1)}",
            strict=False
        )

        gateway = ipaddress.ip_address(gateway_match.group(1))

        return gateway not in network

    except ValueError:
        return False


def check_interface_down(text):
    """Detect interfaces or links that are down."""
    indicators = [
        "administratively down",
        "down/down",
        "interface is down",
        "line protocol down",
        "subinterface"
    ]

    text_lower = text.lower()

    if "subinterface" in text_lower and "is down" in text_lower:
        return True

    return any(x in text_lower for x in indicators)


def check_missing_vlan(text):
    """Detect VLANs that do not exist."""
    return bool(
        re.search(
            r'VLAN\s+\d+\s+does not exist',
            text,
            re.IGNORECASE
        )
    )


def check_wrong_vlan(text):
    """Detect incorrect VLAN assignments."""
    text_lower = text.lower()

    return (
        "assigned vlan 10" in text_lower
        or "assigned vlan 40" in text_lower
        or "wrong vlan" in text_lower
        or "assigned to the wrong vlan" in text_lower
        or "wrong vlan" in text_lower
    )


def check_missing_route(text):
    """Detect missing routing information."""
    patterns = [
        r'route.*is missing',
        r'no route.*for',
        r'no route.*to',
        r'no route back',
        r'no 0\.0\.0\.0/0 route',
        r'default route.*missing'
    ]

    return any(
        re.search(pattern, text, re.IGNORECASE)
        for pattern in patterns
    )


def check_invalid_mask(text):
    """Detect invalid or explicitly incompatible subnet masks."""
    text_lower = text.lower()

    if "incompatible subnet mask" in text_lower:
        return True

    mask_match = re.search(
        r'(?:Mask|mask)\s+(\d+\.\d+\.\d+\.\d+)',
        text
    )

    if not mask_match:
        return False

    try:
        ipaddress.ip_network(
            "192.168.1.1/" + mask_match.group(1),
            strict=False
        )
        return False

    except ValueError:
        return True


def check_trunk_vlan(text):
    """Detect VLANs missing from trunk configuration."""
    text_lower = text.lower()

    return (
        "not listed as allowed" in text_lower
        or "not allowed on the trunk" in text_lower
        or "missing from the trunk allowed list" in text_lower
    )


def check_acl_block(text):
    """Detect ACL rules that may block traffic."""
    text_lower = text.lower()

    return (
        "deny ip" in text_lower
        or "deny tcp" in text_lower
        or "acl blocks" in text_lower
        or "acl block" in text_lower
        or "blocks internet-bound" in text_lower
    )


def check_nat_problem(text):
    """Detect common NAT configuration problems."""
    text_lower = text.lower()

    return (
        "not included in nat" in text_lower
        or "inside/outside" in text_lower
        or (
            "nat" in text_lower
            and "wrong interfaces" in text_lower
        )
    )


def check_dns_problem(text):
    """Detect DNS-related configuration or connectivity issues."""
    text_lower = text.lower()

    return (
        "dns service" in text_lower
        or "dns record" in text_lower
        or "dns server" in text_lower
    )


def check_dhcp_problem(text):
    """Detect DHCP-related problems."""
    text_lower = text.lower()

    return (
        "dhcp pool" in text_lower
        or "dhcp service" in text_lower
    )


def check_wireless_problem(text):
    """Detect wireless-related problems."""
    text_lower = text.lower()

    return (
        "ssid" in text_lower
        or "wireless" in text_lower
        or "guest network" in text_lower
    )


def analyze_case(case):
    """
    Run deterministic checks against the case evidence.
    The expected fault is NOT used to generate findings.
    """

    text = " ".join([
        case["symptom"],
        case["topology"],
        case["show_outputs"]
    ])

    findings = []

    if check_duplicate_ip(text):
        findings.append("Duplicate IP detected")

    if check_gateway_mismatch(text):
        findings.append("Gateway mismatch detected")

    if check_invalid_mask(text):
        findings.append("Invalid subnet mask detected")

    if check_interface_down(text):
        findings.append(
            "Interface/link down condition detected"
        )

    if check_missing_vlan(text):
        findings.append("Missing VLAN detected")

    if check_wrong_vlan(text):
        findings.append(
            "Incorrect VLAN assignment detected"
        )

    if check_missing_route(text):
        findings.append("Missing route detected")

    if check_trunk_vlan(text):
        findings.append(
            "Trunk VLAN configuration issue detected"
        )

    if check_acl_block(text):
        findings.append(
            "ACL blocking condition detected"
        )

    if check_nat_problem(text):
        findings.append(
            "NAT configuration issue detected"
        )

    if check_dns_problem(text):
        findings.append(
            "DNS-related condition detected"
        )

    if check_dhcp_problem(text):
        findings.append(
            "DHCP-related condition detected"
        )

    if check_wireless_problem(text):
        findings.append(
            "Wireless-related condition detected"
        )

    if not findings:
        findings.append(
            "No deterministic issue detected"
        )

    return findings


def main():
    print("=" * 65)
    print("                 NETSAGE AI RULE CHECKER")
    print("=" * 65)

    total = 0
    detected = 0

    try:
        with open(
            CASES_FILE,
            "r",
            encoding="utf-8"
        ) as file:

            cases = csv.DictReader(file)

            for case in cases:
                total += 1

                print(f"\nCase {case['case_id']}")
                print("-" * 45)

                print(
                    f"Expected fault: "
                    f"{case['expected_fault']}"
                )

                findings = analyze_case(case)

                for finding in findings:
                    print(f"[CHECK] {finding}")

                if findings != [
                    "No deterministic issue detected"
                ]:
                    detected += 1

    except FileNotFoundError:
        print("\nERROR: cases.csv was not found.")
        print(
            "Make sure the file exists in "
            "../data/cases.csv"
        )
        return

    except Exception as e:
        print(f"\nERROR: {e}")
        return

    print("\n" + "=" * 65)
    print(f"Total cases checked: {total}")
    print(
        f"Cases with deterministic findings: "
        f"{detected}"
    )
    print("=" * 65)


if __name__ == "__main__":
    main()
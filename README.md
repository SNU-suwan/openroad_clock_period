# Proper Clock Period Finder for Design Implementation in OpenROAD

## Description
This code finds a proper clock period for design implementation in OpenROAD by exploring the clock period that satisfies the following condition:


$`\text{lower\_bound} \cdot \text{initial\_clock\_period} \leq \text{worst\_slack} \leq \text{upper\_bound} \cdot \text{initial\_clock\_period}`$


## Arguments
The script accepts the following command-line arguments:

- `-d`: The name of the design.
- `-p`: Platform (technology).
- `-c`: Initial clock period.
- `-lb`: Lower bound relative to the clock period.
- `-ub`: Upper bound relative to the clock period.

### Example Usage
```bash
python3 main.py -d gcd -p nangate45 -c 300 -lb -0.8 -ub 1.2

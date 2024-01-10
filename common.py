from starkware import FieldElement, X

#=============================================================================
# Public parameter

def public_parameter():
    # `g` is chosen as a public parameter.
    g = FieldElement.generator() ** (3 * (2 ** 20))
    return g

# Generate group elements of size 1024
def generate_group( g: FieldElement ):
    return [g ** i for i in range(1024)]


#=============================================================================
# Circuit setup
# - Only used by the prover.
# - May be public or private.

# The Circuit
def fibSq(x):
    a = [FieldElement(1), FieldElement(x)]
    while len(a) < 1023:
        a.append(a[-2] * a[-2] + a[-1] * a[-1])
    return a

# Generates 3 rational functions based on the circuit constraints and
# the function `f` representing the computational trace.
def get_rational_functions( f ):
    g = public_parameter()

    # p0: First Constraint (input)
    numer0 = f - 1
    denom0 = X - 1
    p0 = numer0 / denom0

    # p1: Second Constraint (result)
    numer1 = f - 2338775057
    denom1 = X - g**1022
    p1 = numer1 / denom1

    # p2: Third Constraint (sequence steps)
    # Note: slow!
    numer2 = f(g**2 * X) - f(g * X)**2 - f**2
    denom2 = (X**1024 - 1) / ((X - g**1021) * (X - g**1022) * (X - g**1023))
    p2 = numer2 / denom2

    return p0, p1, p2

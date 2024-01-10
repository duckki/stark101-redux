from starkware import FieldElement, Polynomial, X, interpolate_poly, MerkleTree, Channel
from common import public_parameter, generate_group, fibSq, get_rational_functions

#=============================================================================
# FRI commitment utilities

def next_fri_domain(fri_domain):
    return [x ** 2 for x in fri_domain[:len(fri_domain) // 2]]

def next_fri_polynomial(poly,  beta):
    odd_coefficients = poly.poly[1::2]
    even_coefficients = poly.poly[::2]
    odd = beta * Polynomial(odd_coefficients)
    even = Polynomial(even_coefficients)
    return odd + even

def next_fri_layer(poly, domain, beta):
    next_poly = next_fri_polynomial(poly, beta)
    next_domain = next_fri_domain(domain)
    next_layer = [next_poly(x) for x in next_domain]
    return next_poly, next_domain, next_layer

def fri_commit(domain, f_merkle, cp, channel):
    cp_eval = [cp(x) for x in domain]
    cp_merkle = MerkleTree(cp_eval)
    channel.send( 'commit_f_merkle', f_merkle.root )
    channel.send( 'commit_cp_merkle', cp_merkle.root )

    fri_polys = [cp]
    fri_domains = [domain]
    fri_layers = [cp_eval]
    fri_merkles = [cp_merkle]
    while fri_polys[-1].degree() > 0:
        beta = channel.receive_random_field_element()
        next_poly, next_domain, next_layer = next_fri_layer(fri_polys[-1], fri_domains[-1], beta)
        fri_polys.append(next_poly)
        fri_domains.append(next_domain)
        fri_layers.append(next_layer)
        fri_merkles.append(MerkleTree(next_layer))
        channel.send( 'commit_cp_merkle', fri_merkles[-1].root )

    channel.send( 'commit_cp_final', str(fri_polys[-1].poly[0]) )
    return fri_polys, fri_domains, fri_layers, fri_merkles

def decommit_on_fri_layers(fri_layers, fri_merkles, idx, channel):
    for layer, merkle in zip(fri_layers[:-1], fri_merkles[:-1]):
        length = len(layer)
        idx = idx % length
        sib_idx = (idx + length // 2) % length
        channel.send( 'decommit_cp_x', str(layer[idx]) ) # cp_i(x)
        channel.send( 'decommit_cp_x_auth_path', merkle.get_authentication_path(idx) )
        channel.send( 'decommit_cp_neg_x', str(layer[sib_idx]) ) # cp_i(-x)
        channel.send( 'decommit_cp_neg_x_auth_path', merkle.get_authentication_path(sib_idx) )

    # The final layer is expected to be a constant.
    channel.send( 'decommit_cp_final', str(fri_layers[-1][0]) )

def fri_decommit(f_eval, f_merkle, fri_layers, fri_merkles, idx, channel):
    assert idx + 16 < len(f_eval), f'query index: {idx} is out of range. Length of layer: {len(f_eval)}.'
    channel.send( 'decommit_x_index', str(idx) ) # index for x
    channel.send( 'decommit_f_x', str(f_eval[idx]) ) # f(x)
    channel.send( 'decommit_f_x_auth_path', f_merkle.get_authentication_path(idx) ) # auth path for f(x)
    channel.send( 'decommit_f_gx', str(f_eval[idx + 8]) ) # f(gx)
    channel.send( 'decommit_f_gx_auth_path', f_merkle.get_authentication_path(idx + 8) ) # auth path for f(gx)
    channel.send( 'decommit_f_ggx', str(f_eval[idx + 16]) ) # f(g^2x)
    channel.send( 'decommit_f_ggx_auth_path', f_merkle.get_authentication_path(idx + 16) ) # auth path for f(g^2x)
    decommit_on_fri_layers(fri_layers, fri_merkles, idx, channel)


#=============================================================================
# For testing

# Returns the deduced `cp(x)` from decommitted f(x), f(gx), f(g^2x) values.
# - This simulates what the verifier would compute.
def deduce_cp( g, x, f_x, f_gx, f_ggx, alpha0, alpha1, alpha2 ):
    p0_x = (f_x - 1) / (x - 1)
    p1_x = (f_x - 2338775057) / (x - g**1022)
    p2_x_denom = (x**1024 - 1) / ((x - g**1021) * (x - g**1022) * (x - g**1023))
    p2_x = (f_ggx - f_gx**2 - f_x**2) / p2_x_denom
    return alpha0 * p0_x + alpha1 * p1_x + alpha2 * p2_x

def check_decommit( g, f_domain, f_eval, cp, fri_layers, alpha0, alpha1, alpha2, idx ):
    x = f_domain[idx]
    cp_x = cp(x)
    deduced_cp_x = deduce_cp( g, x, f_eval[idx], f_eval[idx + 8], f_eval[idx + 16], alpha0, alpha1, alpha2 )
    assert deduced_cp_x == cp_x
    assert deduced_cp_x == fri_layers[0][idx]

    idx2 = (idx + (len(f_domain) // 2)) % len(f_domain) # index for -x
    cp_x2 = cp(-x)
    deduced_cp_x2 = deduce_cp( g, -x, f_eval[idx2], f_eval[idx2 + 8], f_eval[idx2 + 16], alpha0, alpha1, alpha2 )
    assert deduced_cp_x2 == cp_x2
    assert deduced_cp_x2 == fri_layers[0][idx2]


#=============================================================================
# Prover

def prove(channel):
    # The secret witness and computational trace.
    witness = 3141592
    trace = fibSq(witness)

    # Setup from the public parameter.
    g = public_parameter()
    G = generate_group( g )

    # Create the polynomial representing the trace.
    # Note: G may be longer than the trace.
    print( "Polynomial interpolation..." )
    f = interpolate_poly( G[:len(trace)], trace )

    # Low Degree Extension
    print( "Low Degree Extension..." )
    k = len(G) * 8
    w = FieldElement.generator()
    h = w ** ((2 ** 30 * 3) // k)
    H = [h ** i for i in range(k)] # Primitive k-th root of unity (h^k = 1)
    f_domain = [w * x for x in H] # a coset of a group of order k.
    f_eval = [f(d) for d in f_domain] # Reed-Solomon codeword
    f_merkle = MerkleTree(f_eval)

    # Compute the composition polynomial (CP).
    print( "Compute the CP..." )
    p0, p1, p2 = get_rational_functions( f )
    alpha0 = channel.receive_random_field_element()
    alpha1 = channel.receive_random_field_element()
    alpha2 = channel.receive_random_field_element()
    cp = alpha0*p0 + alpha1*p1 + alpha2*p2

    # Commit `f` and CP.
    print( "FRI commit..." )
    _, _, fri_layers, fri_merkles = fri_commit(f_domain, f_merkle, cp, channel)

    # Evaluate `f` and CP at random points.
    for _ in range(3):
        # Get a random index from the verifier and send the corresponding decommitment.
        r = channel.receive_random_int(0, 8191-16)
        print( f"FRI decommit at index {r}" )
        fri_decommit(f_eval, f_merkle, fri_layers, fri_merkles, r, channel)

        # Sanity check
        check_decommit( g, f_domain, f_eval, cp, fri_layers, alpha0, alpha1, alpha2, r )


#=============================================================================
# The main function

import json

def main():
    channel = Channel()

    prove(channel)

    filename='proof.json'
    with open(filename, 'w') as f:
        json.dump( channel.proof, f )
        print( f"Proof written to \"{filename}\"" )

if __name__ == '__main__':
    main()

# STARK101 Redux

This repo is a reproduction of the original stark101 zk-SNARK tutorial (2019) ([Website](https://starkware.co/stark-101/), [github repo](https://github.com/starkware-industries/stark101)). It has the same logic as the original, but the main tutorial code has been refactored for clarity.

## Repo Layout

Directory structure:
```
├── starkware
│   ├── __init__.py
│   ├── channel.py
│   ├── field.py
│   ├── list_utils.py
│   ├── merkle.py
│   └── polynomial.py
├── common.py
└── prover.py
```
The utility files like `field.py`, `polynomial`, `channel.py` are moved to the `starkware` directory. Those files are not modified, except for the `channel.py`, where a new `tag` argument was added to the `Channel.send` method.

The `common.py` file contains the setup procedures, including the public parameters and the circuit definition.

The `prover.py` file contains the main code combining all 4 parts of the original tutorial series. Instead of being a separate Jupyter notebooks, it's designed to be a single application that outputs a `proof.json` file as zk-SNARK proof.


## How to follow the original tutorial with this repo

The original tutorial series has 4 parts. I'll explain which part of this repo corresponds to each tutorial part.

### Part 1

The part 1 defines the program/circuit in question - `fibSq` and it's defined in the `common.py`. The public parameter `g` and the group elements generator `G` are also definined in `common.py`, since they will be shared with the verifier.

Other code related to the part 1 can be found in the `prove` function in `prover.py`.

```python
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
```

### Part 2

The part 2 constructs the 3 rational functions `p0`, `p1` and `p2`, based on the circuit constraints. That code is in the `get_rational_functions` function in `common.py`, because they are directly derived from the circuit `fibSq` and belongs to the SNARK setup process.

The computation of CP is a short code as below in the `prove` function.

```python
    # Compute the composition polynomial (CP).
    print( "Compute the CP..." )
    p0, p1, p2 = get_rational_functions( f )
    alpha0 = channel.receive_random_field_element()
    alpha1 = channel.receive_random_field_element()
    alpha2 = channel.receive_random_field_element()
    cp = alpha0*p0 + alpha1*p1 + alpha2*p2
```

### Part 3

The part 3 is about the FRI commitment. The original `FriCommit` function has been renamed as `fri_commit` and it resides in the `prover.py`, along with its subroutines.

Then, the `prover` function just invokes `fri_commit` as below.

```python
    # Commit `f` and CP.
    print( "FRI commit..." )
    _, _, fri_layers, fri_merkles = fri_commit(f_domain, f_merkle, cp, channel)
```

### Part 4

The part 4 is about the decommitment. I renamed the original `decommit_on_query` function as `fri_decommit` and it's also in `prover.py`.

The decommit process is as following:

```python
    # Evaluate `f` and CP at random points.
    for _ in range(3):
        # Get a random index from the verifier and send the corresponding decommitment.
        r = channel.receive_random_int(0, 8191-16)
        print( f"FRI decommit at index {r}" )
        fri_decommit(f_eval, f_merkle, fri_layers, fri_merkles, r, channel)

        # Sanity check
        check_decommit( g, f_domain, f_eval, cp, fri_layers, alpha0, alpha1, alpha2, r )
```

I added `check_decommit` function for testing. The function performs a part of verification to confirm the proof is correctly constructed (at least partially).

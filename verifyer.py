import json

from common import public_parameter, generate_group


def verify( proof ):
    print( "Verifying..." )
    pass

#=============================================================================
# The main function

def main():
    with open('proof.json', 'r') as f:
        proof = json.load( f )
        verify( proof )

if __name__ == '__main__':
    main()

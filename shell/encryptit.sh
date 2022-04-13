#!/bin/bash

while getopts ":k:o:" arg; do
	case ${arg} in
		k)
			key=${OPTARG}
			;;
		o)
			outfile=${OPTARG}
			;;
		\?)
			echo "unspecified argument -${OPTARG}"
			exit 1
			;;
		:)
			echo "Invalid option: $OPTARG requires an argument" 1>&2
			exit 1
			;;
	esac
done
shift $((OPTIND -1))
if [ !  -f $1 ];
	then
		echo "the file: $1 doesn't exist"
else
	if [ -z $key ];
	then
		echo "need to specify a key using -k";
		exit 1;
	fi;
	if [ -z $outfile ];
	then
		outfile="${1}.enc";
	fi;
	
	echo "encrypting the contents of $1 to ${outfile} with ${key}"
	openssl aes-256-cbc -e -in $1 -out ${outfile} -kfile ${key} -pbkdf2
	openssl aes-256-cbc -d -in ${outfile} -out "${outfile}.test" -kfile ${key} -pbkdf2

	if cmp -s -- $1 "${outfile}.test"; then
		echo "file contents encrypted"
		rm "${outfile}.test"
		rm $1
	fi
		
fi


process GATK_HAPLOTYPECALLER {
    tag "${meta.id}"
    label 'process_medium'
    container 'broadinstitute/gatk:4.5.0.0'

    input:
    tuple val(meta), path(bam), path(bai)
    path fasta
    path fasta_fai
    path fasta_dict
    path dbsnp
    path dbsnp_tbi
    path intervals

    output:
    tuple val(meta), path('*.g.vcf.gz'),     emit: gvcf
    tuple val(meta), path('*.g.vcf.gz.tbi'), emit: tbi
    path 'versions.yml',                     emit: versions

    script:
    def prefix       = meta.id
    def avail_mem    = (task.memory.giga * 0.8).intValue()
    def interval_cmd = intervals ? "--intervals ${intervals}" : ""
    """
    gatk --java-options "-Xmx${avail_mem}g" HaplotypeCaller \\
        --input ${bam} \\
        --reference ${fasta} \\
        --dbsnp ${dbsnp} \\
        --output ${prefix}.g.vcf.gz \\
        --emit-ref-confidence GVCF \\
        --sample-ploidy 2 \\
        --standard-min-confidence-threshold-for-calling 30 \\
        --annotation MappingQualityRankSumTest \\
        --annotation ReadPosRankSumTest \\
        --annotation FisherStrand \\
        --annotation QualByDepth \\
        --annotation StrandOddsRatio \\
        --native-pair-hmm-threads ${task.cpus} \\
        ${interval_cmd} \\
        --tmp-dir .

    cat <<-VERSIONS > versions.yml
    "${task.process}":
        gatk: \$(gatk --version 2>&1 | grep -o '[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+\\.[0-9]\\+' | head -1)
    VERSIONS
    """

    stub:
    def prefix = meta.id
    """
    touch ${prefix}.g.vcf.gz ${prefix}.g.vcf.gz.tbi
    cat <<-VERSIONS > versions.yml
    "${task.process}":
        gatk: 4.5.0.0
    VERSIONS
    """
}
